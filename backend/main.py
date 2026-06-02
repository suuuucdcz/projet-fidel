from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from db import supabase
from wallet_service import wallet_service
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Loyalty Cards Agency Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    email: str
    password: str

class GenerateCardRequest(BaseModel):
    first_name: str
    last_name: str
    pin_code: str
    action: str = "signup"  # "signup" or "login"

class ScanRequest(BaseModel):
    customer_id: str
    merchant_id: str

class PushMessageRequest(BaseModel):
    merchant_id: str
    header: str
    body: str

class UpdateOfferRequest(BaseModel):
    merchant_id: str
    reward_threshold: int
    reward_description: str

class CreateMerchantRequest(BaseModel):
    name: str
    email: str
    password: str

@app.get("/")
def read_root():
    return {"message": "Agency Platform API is running"}

@app.post("/merchants/login")
def login(req: LoginRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection is not configured")

    response = supabase.table("merchants").select("*").eq("email", req.email).execute()
    if not response.data:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    
    merchant = response.data[0]
    
    # Check password
    if not pwd_context.verify(req.password, merchant["password_hash"]):
        # Special fallback for the old test account which wasn't hashed
        if req.password != merchant["password_hash"]:
             raise HTTPException(status_code=401, detail="Identifiants incorrects")
    
    return {"merchant_id": merchant["id"]}

@app.get("/merchants/settings/{merchant_id}")
def get_merchant_settings(merchant_id: str):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
        
    m_res = supabase.table("merchants").select("name, reward_threshold, reward_description").eq("id", merchant_id).execute()
    if not m_res.data:
        raise HTTPException(status_code=404, detail="Merchant not found")
        
    return m_res.data[0]

@app.post("/cards/generate/{merchant_id}")
def generate_card(merchant_id: str, req: GenerateCardRequest):
    """
    Called by the web registration form.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Fetch merchant info to get reward rules
    m_res = supabase.table("merchants").select("*").eq("id", merchant_id).execute()
    if not m_res.data:
        raise HTTPException(status_code=404, detail="Merchant not found")
    merchant = m_res.data[0]

    # Check if customer already exists (globally across merchants)
    existing_customers = supabase.table("customers").select("id, pin_code").eq("first_name", req.first_name).eq("last_name", req.last_name).execute()
    
    customer_id = None
    points = 0
    
    if existing_customers.data:
        if req.action == "signup":
            raise HTTPException(status_code=409, detail="Ce compte existe déjà ! Veuillez utiliser l'onglet 'J'ai déjà une carte' pour vous reconnecter.")
            
        # User found with this name. Verify PIN.
        matched_cust = None
        for cust in existing_customers.data:
            if cust.get("pin_code") == req.pin_code:
                matched_cust = cust
                break
                
        if not matched_cust:
            # Wrong PIN
            raise HTTPException(status_code=401, detail="Code PIN incorrect pour ce nom.")
            
        cid = matched_cust["id"]
        # Check if they already have a card for THIS merchant
        card_check = supabase.table("loyalty_cards").select("*").eq("customer_id", cid).eq("merchant_id", merchant_id).execute()
        
        if card_check.data:
            customer_id = cid
            points = card_check.data[0]["points"]
        else:
            customer_id = cid
            supabase.table("loyalty_cards").insert({
                "merchant_id": merchant_id,
                "customer_id": customer_id,
                "points": 0
            }).execute()
            points = 0
                
    if not customer_id:
        if req.action == "login":
            raise HTTPException(status_code=404, detail="Aucun compte trouvé à ce nom. Veuillez créer une nouvelle carte.")
            
        # Create NEW customer profile
        customer_res = supabase.table("customers").insert({
            "first_name": req.first_name,
            "last_name": req.last_name,
            "pin_code": req.pin_code
        }).execute()
        customer_id = customer_res.data[0]["id"]
        
        # Link customer to merchant
        supabase.table("loyalty_cards").insert({
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "points": 0
        }).execute()
        points = 0

    # Generate Wallet Link with merchant rules
    link = wallet_service.generate_jwt_url(
        customer_id=customer_id, 
        points=points, 
        merchant_name=merchant["name"],
        threshold=merchant["reward_threshold"],
        reward_desc=merchant["reward_description"],
        first_name=req.first_name
    )
    
    return {"wallet_link": link, "customer_id": customer_id}

@app.post("/cards/scan")
def scan_card(req: ScanRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Fetch current points
    card_res = supabase.table("loyalty_cards").select("points").eq("merchant_id", req.merchant_id).eq("customer_id", req.customer_id).execute()
    if not card_res.data:
        raise HTTPException(status_code=404, detail="Loyalty card not found")
        
    current_points = card_res.data[0]["points"]
    
    # Fetch merchant rules
    m_res = supabase.table("merchants").select("*").eq("id", req.merchant_id).execute()
    merchant = m_res.data[0]
    threshold = merchant["reward_threshold"]
    reward_desc = merchant["reward_description"]

    new_points = current_points + 1
    reward_triggered = False

    if new_points >= threshold:
        # Threshold reached! Reward the user and reset points.
        reward_triggered = True
        new_points = 0 # Reset cycle

    # Update DB
    supabase.table("loyalty_cards").update({"points": new_points}).eq("merchant_id", req.merchant_id).eq("customer_id", req.customer_id).execute()
    
    # Log the scan
    supabase.table("scan_logs").insert({
        "merchant_id": req.merchant_id,
        "customer_id": req.customer_id,
        "action_type": "REWARD" if reward_triggered else "SCAN",
        "points_added": 1
    }).execute()
    
    # Push update to Google Wallet
    try:
        if reward_triggered:
            # Send a special notification for the reward
            wallet_service.update_points(req.customer_id, new_points, threshold, reward_desc, reward_unlocked=True)
        else:
            wallet_service.update_points(req.customer_id, new_points, threshold, reward_desc, reward_unlocked=False)
    except Exception as e:
        print(f"Warning: Failed to push update to wallet: {e}")
        
    return {"status": "success", "new_points": new_points, "reward_triggered": reward_triggered, "reward_desc": reward_desc if reward_triggered else None}

@app.post("/marketing/push")
def push_marketing(req: PushMessageRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
        
    cards_res = supabase.table("loyalty_cards").select("customer_id").eq("merchant_id", req.merchant_id).execute()
    customers = cards_res.data
    
    sent = 0
    for card in customers:
        try:
            wallet_service.push_marketing_message(card["customer_id"], req.header, req.body)
            sent += 1
            
            # Log the push
            supabase.table("scan_logs").insert({
                "merchant_id": req.merchant_id,
                "customer_id": card["customer_id"],
                "action_type": "PUSH_CAMPAIGN",
                "points_added": 0
            }).execute()
        except Exception as e:
            print(f"Failed to send to {card['customer_id']}: {e}")
    if sent == 0 and len(customers) > 0:
        raise HTTPException(status_code=500, detail="Echec de l'envoi Google Wallet")
        
    return {"status": "success", "sent": sent, "total": len(customers)}

# ==========================================
# SUPER-ADMIN / DASHBOARD ROUTES
# ==========================================

@app.get("/dashboard/stats/{merchant_id}")
def get_dashboard_stats(merchant_id: str):
    if not supabase: return {"total_customers": 0, "total_points": 0}
    res = supabase.table("loyalty_cards").select("points").eq("merchant_id", merchant_id).execute()
    cards = res.data
    return {
        "total_customers": len(cards), 
        "total_points": sum(card["points"] for card in cards)
    }

@app.get("/dashboard/customers/{merchant_id}")
def get_dashboard_customers(merchant_id: str):
    if not supabase: return []
    res = supabase.table("loyalty_cards").select("customer_id, points, created_at, customers(first_name, last_name)").eq("merchant_id", merchant_id).order("created_at", desc=True).execute()
    return res.data

@app.get("/dashboard/admin/merchants")
def get_all_merchants():
    """Fetches all merchants for the Super-Admin Agency dashboard"""
    if not supabase: return []
    res = supabase.table("merchants").select("*").order("created_at", desc=True).execute()
    return res.data

@app.post("/dashboard/admin/update_offer")
def update_merchant_offer(req: UpdateOfferRequest):
    """Update reward threshold and description for a merchant"""
    if not supabase: raise HTTPException(status_code=500)
    supabase.table("merchants").update({
        "reward_threshold": req.reward_threshold,
        "reward_description": req.reward_description
    }).eq("id", req.merchant_id).execute()
    return {"status": "success"}

@app.post("/dashboard/admin/merchants/create")
def create_merchant(req: CreateMerchantRequest):
    """Create a new merchant account with hashed password"""
    if not supabase: raise HTTPException(status_code=500)
    
    # Check if exists
    existing = supabase.table("merchants").select("id").eq("email", req.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Un commerçant avec cet email existe déjà")
        
    hashed_pwd = pwd_context.hash(req.password)
    
    res = supabase.table("merchants").insert({
        "name": req.name,
        "email": req.email,
        "password_hash": hashed_pwd
    }).execute()
    
    return {"status": "success", "merchant_id": res.data[0]["id"]}

@app.get("/dashboard/admin/logs/{merchant_id}")
def get_merchant_logs(merchant_id: str):
    if not supabase: return []
    res = supabase.table("scan_logs").select("action_type, created_at, points_added, customers(first_name, last_name)").eq("merchant_id", merchant_id).order("created_at", desc=True).limit(50).execute()
    return res.data

@app.delete("/dashboard/admin/merchants/{merchant_id}")
def delete_merchant(merchant_id: str):
    if not supabase: raise HTTPException(status_code=500)
    supabase.table("merchants").delete().eq("id", merchant_id).execute()
    return {"status": "success"}

@app.delete("/dashboard/admin/customers/{merchant_id}/{customer_id}")
def delete_customer_from_merchant(merchant_id: str, customer_id: str):
    if not supabase: raise HTTPException(status_code=500)
    # Delete the customer entirely from the database
    # ON DELETE CASCADE will automatically remove their loyalty_cards and scan_logs
    supabase.table("customers").delete().eq("id", customer_id).execute()
    return {"status": "success"}

