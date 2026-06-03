from fastapi import APIRouter, HTTPException, Depends
from schemas import LoginRequest, MerchantSettingsUpdate
from db import supabase
from auth import create_merchant_token, get_current_merchant_id
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/merchants", tags=["merchants"])

@router.post("/login")
def login(req: LoginRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection is not configured")

    response = supabase.table("merchants").select("*").eq("email", req.email).execute()
    if not response.data:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    
    merchant = response.data[0]

    # Check password. verify() can raise if the stored value isn't a valid bcrypt
    # hash (e.g. a legacy plaintext seed row) — treat any such case as invalid.
    try:
        valid = pwd_context.verify(req.password, merchant["password_hash"])
    except Exception:
        valid = False
    if not valid:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    token = create_merchant_token(merchant["id"])
    return {"merchant_id": merchant["id"], "access_token": token, "token_type": "bearer"}

@router.get("/settings/{merchant_id}")
def get_merchant_settings(merchant_id: str):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
        
    m_res = supabase.table("merchants").select("name, reward_threshold, reward_description, color_hex, logo_url, hero_url, program_name, points_label, phone, website").eq("id", merchant_id).execute()
    if not m_res.data:
        raise HTTPException(status_code=404, detail="Merchant not found")

    return m_res.data[0]


@router.post("/settings")
def update_my_settings(req: MerchantSettingsUpdate, merchant_id: str = Depends(get_current_merchant_id)):
    """Self-service offer update for the authenticated merchant (used by the scanner
    app). The merchant id comes from the session token, so a merchant can only edit
    its own offer. Design fields (color/logo/hero) are managed by the agency dashboard."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    supabase.table("merchants").update({
        "reward_threshold": req.reward_threshold,
        "reward_description": req.reward_description,
    }).eq("id", merchant_id).execute()
    return {"status": "success"}
