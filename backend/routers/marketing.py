from fastapi import APIRouter, HTTPException
from schemas import PushMessageRequest
from db import supabase
from wallet_service import wallet_service

router = APIRouter(prefix="/marketing", tags=["marketing"])

@router.post("/push")
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
