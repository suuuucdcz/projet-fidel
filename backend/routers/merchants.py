from fastapi import APIRouter, HTTPException
from schemas import LoginRequest
from db import supabase
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
    
    # Check password
    if not pwd_context.verify(req.password, merchant["password_hash"]):
        # Special fallback for the old test account which wasn't hashed
        if req.password != merchant["password_hash"]:
             raise HTTPException(status_code=401, detail="Identifiants incorrects")
    
    return {"merchant_id": merchant["id"]}

@router.get("/settings/{merchant_id}")
def get_merchant_settings(merchant_id: str):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
        
    m_res = supabase.table("merchants").select("name, reward_threshold, reward_description, color_hex, logo_url, hero_url").eq("id", merchant_id).execute()
    if not m_res.data:
        raise HTTPException(status_code=404, detail="Merchant not found")
        
    return m_res.data[0]
