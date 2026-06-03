import os

from fastapi import APIRouter, HTTPException, Header, Depends
from schemas import UpdateOfferRequest, CreateMerchantRequest
from db import supabase
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/dashboard", tags=["admin"])

# Minimal agency-admin guard: endpoints that manage merchants/customers globally
# require the X-Admin-Token header to match the ADMIN_TOKEN env var.
# If ADMIN_TOKEN is unset we stay backward-compatible (open) but warn loudly, so an
# existing deployment keeps working until the env var is configured on Render.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


def require_admin(x_admin_token: str | None = Header(default=None)):
    if not ADMIN_TOKEN:
        print("WARNING: ADMIN_TOKEN not set — agency admin endpoints are UNPROTECTED. "
              "Set ADMIN_TOKEN in the backend environment to enable the guard.")
        return
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Jeton administrateur invalide")

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

@router.get("/admin/merchants", dependencies=[Depends(require_admin)])
def get_all_merchants():
    """Fetches all merchants for the Super-Admin Agency dashboard"""
    if not supabase: return []
    res = supabase.table("merchants").select("*").order("created_at", desc=True).execute()
    return res.data

@router.post("/admin/update_offer")
def update_merchant_offer(req: UpdateOfferRequest):
    """Update reward/design fields for a merchant. Only the fields actually provided
    are written, so a partial caller (e.g. the scanner app editing just the offer)
    never erases the design fields (color/logo/hero) it didn't send."""
    if not supabase: raise HTTPException(status_code=500)

    updatable = ("reward_threshold", "reward_description", "color_hex", "logo_url", "hero_url")
    updates = {f: getattr(req, f) for f in updatable if getattr(req, f) is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Aucun champ à mettre à jour")

    supabase.table("merchants").update(updates).eq("id", req.merchant_id).execute()
    return {"status": "success"}

@router.post("/admin/merchants/create", dependencies=[Depends(require_admin)])
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

@router.get("/admin/logs/{merchant_id}", dependencies=[Depends(require_admin)])
def get_merchant_logs(merchant_id: str):
    if not supabase: return []
    res = supabase.table("scan_logs").select("action_type, created_at, points_added, customers(first_name, last_name)").eq("merchant_id", merchant_id).order("created_at", desc=True).limit(50).execute()
    return res.data

@router.delete("/admin/merchants/{merchant_id}", dependencies=[Depends(require_admin)])
def delete_merchant(merchant_id: str):
    if not supabase: raise HTTPException(status_code=500)
    supabase.table("merchants").delete().eq("id", merchant_id).execute()
    return {"status": "success"}

@router.delete("/admin/customers/{merchant_id}/{customer_id}", dependencies=[Depends(require_admin)])
def delete_customer_from_merchant(merchant_id: str, customer_id: str):
    if not supabase: raise HTTPException(status_code=500)
    # Delete the customer entirely from the database
    # ON DELETE CASCADE will automatically remove their loyalty_cards and scan_logs
    supabase.table("customers").delete().eq("id", customer_id).execute()
    return {"status": "success"}
