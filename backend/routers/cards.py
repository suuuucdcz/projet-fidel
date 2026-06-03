from fastapi import APIRouter, HTTPException
from schemas import GenerateCardRequest, ScanRequest
from db import supabase
from wallet_service import wallet_service

router = APIRouter(prefix="/cards", tags=["cards"])

@router.post("/generate/{merchant_id}")
def generate_card(merchant_id: str, req: GenerateCardRequest):
    """
    Called by the web registration form to generate a loyalty card
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

@router.post("/scan")
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
        new_points = 0

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
        wallet_service.update_points(req.customer_id, new_points, threshold, reward_desc, reward_unlocked=reward_triggered)
    except Exception as e:
        print(f"Warning: Failed to push update to wallet: {e}")
        
    return {"status": "success", "new_points": new_points, "reward_triggered": reward_triggered, "reward_desc": reward_desc if reward_triggered else None}
