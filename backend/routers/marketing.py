from fastapi import APIRouter, HTTPException, Depends
from schemas import PushMessageRequest
from db import supabase
from auth import get_current_merchant_id
from wallet_service import wallet_service

router = APIRouter(prefix="/marketing", tags=["marketing"])

@router.post("/push")
def push_marketing(req: PushMessageRequest, merchant_id: str = Depends(get_current_merchant_id)):
    # merchant_id comes from the authenticated session token, so a merchant can only
    # broadcast to its own customers.
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    cards_res = supabase.table("loyalty_cards").select("customer_id").eq("merchant_id", merchant_id).execute()
    customers = cards_res.data

    sent = 0
    failed = 0
    last_error = None
    for card in customers:
        try:
            wallet_service.push_marketing_message(card["customer_id"], req.header, req.body)
            sent += 1

            # Log the push
            supabase.table("scan_logs").insert({
                "merchant_id": merchant_id,
                "customer_id": card["customer_id"],
                "action_type": "PUSH_CAMPAIGN",
                "points_added": 0
            }).execute()
        except Exception as e:
            failed += 1
            last_error = str(e)
            print(f"Failed to send to {card['customer_id']}: {e}")

    # If nothing went out at all, surface Google's actual error so the merchant can act
    # (common cause: customers who never tapped "Add to Google Wallet" -> no card object).
    if sent == 0 and len(customers) > 0:
        raise HTTPException(status_code=502, detail=f"Aucune notification envoyée. Détail Google: {last_error}")

    return {"status": "success", "sent": sent, "failed": failed, "total": len(customers)}
