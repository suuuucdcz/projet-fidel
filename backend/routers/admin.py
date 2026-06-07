import os

from fastapi import APIRouter, HTTPException, Header, Depends
from schemas import UpdateOfferRequest, CreateMerchantRequest
from db import supabase
from wallet_service import wallet_service
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
    res = supabase.table("loyalty_cards").select("customer_id, points, balance_cents, created_at, customers(first_name, last_name)").eq("merchant_id", merchant_id).order("created_at", desc=True).execute()
    return res.data

@router.get("/admin/merchants", dependencies=[Depends(require_admin)])
def get_all_merchants():
    """Fetches all merchants for the Super-Admin Agency dashboard"""
    if not supabase: return []
    res = supabase.table("merchants").select("*").order("created_at", desc=True).execute()
    return res.data

@router.post("/admin/update_offer", dependencies=[Depends(require_admin)])
def update_merchant_offer(req: UpdateOfferRequest):
    """Update reward/design fields for a merchant. Only the fields actually provided
    are written, so a partial caller (e.g. the scanner app editing just the offer)
    never erases the design fields (color/logo/hero) it didn't send."""
    if not supabase: raise HTTPException(status_code=500)

    updatable = ("reward_threshold", "reward_description", "color_hex", "logo_url", "hero_url",
                 "program_name", "points_label", "phone", "website", "loyalty_type", "tiers",
                 "cashback_rate")
    updates = {}
    for f in updatable:
        val = getattr(req, f)
        if val is None:
            continue
        if f == "tiers":
            # Pydantic models -> plain dicts for the JSONB column.
            val = [t.model_dump() for t in val]
        updates[f] = val
    if not updates:
        raise HTTPException(status_code=400, detail="Aucun champ à mettre à jour")

    supabase.table("merchants").update(updates).eq("id", req.merchant_id).execute()

    # Generic passes carry their design per-OBJECT, so propagate the design to every
    # card already saved by this merchant's customers. The aggregate result is returned
    # so the dashboard can show whether Google accepted the updates.
    wallet_sync = None
    try:
        m = supabase.table("merchants").select(
            "name, program_name, color_hex, logo_url, hero_url, phone, website"
        ).eq("id", req.merchant_id).execute()
        cards = supabase.table("loyalty_cards").select("customer_id").eq("merchant_id", req.merchant_id).execute()
        customer_ids = [c["customer_id"] for c in (cards.data or [])]
        if m.data:
            mm = m.data[0]
            updated = 0
            last_error = None
            for cid in customer_ids:
                r = wallet_service.update_object_design(
                    cid, mm["name"],
                    program_name=mm.get("program_name") or "",
                    color_hex=mm.get("color_hex") or "",
                    logo_url=mm.get("logo_url") or "",
                    hero_url=mm.get("hero_url") or "",
                    phone=mm.get("phone") or "",
                    website=mm.get("website") or "",
                )
                if r and r.get("ok"):
                    updated += 1
                elif r:
                    last_error = f"HTTP {r.get('status')}: {r.get('error')}"
            wallet_sync = {"ok": last_error is None, "updated": updated, "total": len(customer_ids), "error": last_error}
    except Exception as e:
        print(f"Warning: Wallet design sync failed: {e}")
        wallet_sync = {"ok": False, "updated": 0, "total": 0, "error": str(e)[:400]}

    return {"status": "success", "wallet_sync": wallet_sync}

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

def _delete_orphan_customers(customer_ids):
    """Delete the customers (among customer_ids) that no longer have ANY loyalty card.

    Customers are global (shared across merchants via loyalty_cards), so we only remove
    a customer once they're not linked to any merchant anymore.
    """
    if not supabase or not customer_ids:
        return
    remaining = supabase.table("loyalty_cards").select("customer_id").in_("customer_id", customer_ids).execute()
    still_linked = {r["customer_id"] for r in (remaining.data or [])}
    orphans = [cid for cid in customer_ids if cid not in still_linked]
    if orphans:
        supabase.table("customers").delete().in_("id", orphans).execute()


@router.delete("/admin/merchants/{merchant_id}", dependencies=[Depends(require_admin)])
def delete_merchant(merchant_id: str):
    if not supabase: raise HTTPException(status_code=500)

    # Capture this merchant's customers before deleting (deleting the merchant cascades
    # its loyalty_cards, so we'd lose the link otherwise).
    cards = supabase.table("loyalty_cards").select("customer_id").eq("merchant_id", merchant_id).execute()
    customer_ids = list({c["customer_id"] for c in (cards.data or [])})

    # Deleting the merchant cascades its loyalty_cards and scan_logs.
    supabase.table("merchants").delete().eq("id", merchant_id).execute()

    # Clean up customers who were only at this merchant.
    _delete_orphan_customers(customer_ids)
    return {"status": "success"}

@router.delete("/admin/customers/{merchant_id}/{customer_id}", dependencies=[Depends(require_admin)])
def delete_customer_from_merchant(merchant_id: str, customer_id: str):
    if not supabase: raise HTTPException(status_code=500)

    # Remove only THIS merchant's card + history for the customer (the customer is global).
    supabase.table("loyalty_cards").delete().eq("merchant_id", merchant_id).eq("customer_id", customer_id).execute()
    supabase.table("scan_logs").delete().eq("merchant_id", merchant_id).eq("customer_id", customer_id).execute()

    # If the customer no longer has any card anywhere, delete the global customer record.
    _delete_orphan_customers([customer_id])
    return {"status": "success"}
