from fastapi import APIRouter, HTTPException
from schemas import UpdateOfferRequest, CreateMerchantRequest
from db import supabase
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/dashboard", tags=["admin"])

@router.get("/stats/{merchant_id}")
def get_dashboard_stats(merchant_id: str):
    if not supabase: return {"total_customers": 0, "total_points": 0}
    res = supabase.table("loyalty_cards").select("points").eq("merchant_id", merchant_id).execute()
    cards = res.data
    return {
        "total_customers": len(cards), 
        "total_points": sum(card["points"] for card in cards)
    }

@router.get("/customers/{merchant_id}")
def get_dashboard_customers(merchant_id: str):
    if not supabase: return []
    res = supabase.table("loyalty_cards").select("customer_id, points, created_at, customers(first_name, last_name)").eq("merchant_id", merchant_id).order("created_at", desc=True).execute()
    return res.data

@router.get("/admin/merchants")
def get_all_merchants():
    """Fetches all merchants for the Super-Admin Agency dashboard"""
    if not supabase: return []
    res = supabase.table("merchants").select("*").order("created_at", desc=True).execute()
    return res.data

@router.post("/admin/update_offer")
def update_merchant_offer(req: UpdateOfferRequest):
    """Update reward threshold and description for a merchant"""
    if not supabase: raise HTTPException(status_code=500)
    supabase.table("merchants").update({
        "reward_threshold": req.reward_threshold,
        "reward_description": req.reward_description,
        "color_hex": req.color_hex,
        "logo_url": req.logo_url,
        "hero_url": req.hero_url
    }).eq("id", req.merchant_id).execute()
    return {"status": "success"}

@router.post("/admin/merchants/create")
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

@router.get("/admin/logs/{merchant_id}")
def get_merchant_logs(merchant_id: str):
    if not supabase: return []
    res = supabase.table("scan_logs").select("action_type, created_at, points_added, customers(first_name, last_name)").eq("merchant_id", merchant_id).order("created_at", desc=True).limit(50).execute()
    return res.data

@router.delete("/admin/merchants/{merchant_id}")
def delete_merchant(merchant_id: str):
    if not supabase: raise HTTPException(status_code=500)
    supabase.table("merchants").delete().eq("id", merchant_id).execute()
    return {"status": "success"}

@router.delete("/admin/customers/{merchant_id}/{customer_id}")
def delete_customer_from_merchant(merchant_id: str, customer_id: str):
    if not supabase: raise HTTPException(status_code=500)
    # Delete the customer entirely from the database
    # ON DELETE CASCADE will automatically remove their loyalty_cards and scan_logs
    supabase.table("customers").delete().eq("id", customer_id).execute()
    return {"status": "success"}
