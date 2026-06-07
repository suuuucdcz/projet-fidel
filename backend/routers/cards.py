from fastapi import APIRouter, HTTPException, Depends, Request
from schemas import GenerateCardRequest, ScanRequest, CashbackRequest
from db import supabase
from auth import get_current_merchant_id
from limiter import limiter
from loyalty import compute_scan_result, next_objective, compute_cashback_earn_cents, tier_reward_at
from wallet_service import wallet_service

router = APIRouter(prefix="/cards", tags=["cards"])

@router.post("/generate/{merchant_id}")
@limiter.limit("20/minute")
def generate_card(request: Request, merchant_id: str, req: GenerateCardRequest):
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

    # Show the next goal on the card (handles tier milestones; identical to the simple
    # threshold for points/stamps).
    lt = merchant.get("loyalty_type") or "points"
    obj_threshold, obj_reward = next_objective(
        lt, points, merchant["reward_threshold"], merchant["reward_description"], merchant.get("tiers") or []
    )

    # For cashback cards, the card shows a euro balance rather than points.
    # Money is stored as integer cents; convert to euros only for display.
    balance = 0.0
    bal_res = supabase.table("loyalty_cards").select("balance_cents").eq("merchant_id", merchant_id).eq("customer_id", customer_id).execute()
    if bal_res.data:
        balance = (bal_res.data[0].get("balance_cents") or 0) / 100.0

    # Generate Wallet Link with merchant rules
    link = wallet_service.generate_jwt_url(
        customer_id=customer_id,
        merchant_id=merchant_id,
        points=points,
        merchant_name=merchant["name"],
        threshold=obj_threshold,
        reward_desc=obj_reward,
        first_name=req.first_name,
        color_hex=merchant.get("color_hex", "#FF9800"),
        logo_url=merchant.get("logo_url", ""),
        hero_url=merchant.get("hero_url", ""),
        program_name=merchant.get("program_name") or merchant["name"],
        points_label=merchant.get("points_label") or "Points",
        phone=merchant.get("phone") or "",
        website=merchant.get("website") or "",
        loyalty_type=lt,
        balance=balance
    )
    
    return {"wallet_link": link, "customer_id": customer_id}

@router.post("/scan")
def scan_card(req: ScanRequest, merchant_id: str = Depends(get_current_merchant_id)):
    # merchant_id comes from the authenticated session token, not the request body,
    # so a merchant can only add points to cards belonging to its own account.
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Fetch merchant rules (also validates the merchant exists)
    m_res = supabase.table("merchants").select("*").eq("id", merchant_id).execute()
    if not m_res.data:
        raise HTTPException(status_code=404, detail="Merchant not found")
    merchant = m_res.data[0]
    threshold = merchant["reward_threshold"]
    reward_desc = merchant["reward_description"]
    loyalty_type = merchant.get("loyalty_type") or "points"
    tiers = merchant.get("tiers") or []

    new_points = None
    reward_triggered = False
    reward_unlocked_desc = None  # the reward that was just unlocked (for the message)

    # Fast atomic path for the single-threshold models (points / stamps).
    if loyalty_type in ("points", "stamps"):
        try:
            rpc_res = supabase.rpc("increment_loyalty_points", {
                "p_merchant_id": merchant_id,
                "p_customer_id": req.customer_id,
            }).execute()
            if rpc_res.data:
                row = rpc_res.data[0]
                new_points = row["new_points"]
                reward_triggered = row["reward_triggered"]
                if reward_triggered:
                    reward_unlocked_desc = reward_desc
        except Exception as e:
            print(f"increment_loyalty_points RPC unavailable, using fallback: {e}")

    elif loyalty_type == "tiers" and tiers:
        # Atomic tier increment; reward is derived from the value reached.
        max_threshold = max(t["threshold"] for t in tiers)
        try:
            rpc_res = supabase.rpc("increment_tiers", {
                "p_merchant_id": merchant_id,
                "p_customer_id": req.customer_id,
                "p_max_threshold": max_threshold,
            }).execute()
            if rpc_res.data:
                row = rpc_res.data[0]
                new_points = row["new_points"]
                reward_triggered, reward_unlocked_desc = tier_reward_at(row["reached"], tiers)
        except Exception as e:
            print(f"increment_tiers RPC unavailable, using fallback: {e}")

    # Fallback when the RPC isn't available (or unhandled type): read-modify-write in Python.
    if new_points is None:
        card_res = supabase.table("loyalty_cards").select("points").eq("merchant_id", merchant_id).eq("customer_id", req.customer_id).execute()
        if not card_res.data:
            raise HTTPException(status_code=404, detail="Loyalty card not found")
        current = card_res.data[0]["points"]
        new_points, reward_triggered, reward_unlocked_desc = compute_scan_result(
            loyalty_type, current, threshold, reward_desc, tiers
        )
        supabase.table("loyalty_cards").update({"points": new_points}).eq("merchant_id", merchant_id).eq("customer_id", req.customer_id).execute()

    # Log the scan
    supabase.table("scan_logs").insert({
        "merchant_id": merchant_id,
        "customer_id": req.customer_id,
        "action_type": "REWARD" if reward_triggered else "SCAN",
        "points_added": 1
    }).execute()

    # Push the update to Google Wallet, showing the *next* goal (handles tier milestones).
    next_threshold, next_reward = next_objective(loyalty_type, new_points, threshold, reward_desc, tiers)
    wallet_desc = reward_unlocked_desc if reward_triggered else next_reward
    try:
        wallet_service.update_points(req.customer_id, new_points, next_threshold, wallet_desc, reward_unlocked=reward_triggered, points_label=merchant.get("points_label") or "Points")
    except Exception as e:
        print(f"Warning: Failed to push update to wallet: {e}")

    cust = supabase.table("customers").select("first_name").eq("id", req.customer_id).execute()
    customer_name = cust.data[0]["first_name"] if cust.data else None

    return {"status": "success", "new_points": new_points, "reward_triggered": reward_triggered, "reward_desc": reward_unlocked_desc if reward_triggered else None, "customer_name": customer_name}


@router.get("/info/{customer_id}")
def card_info(customer_id: str, merchant_id: str = Depends(get_current_merchant_id)):
    """Current points + cashback balance of a card, for the authenticated merchant."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    card_res = supabase.table("loyalty_cards").select("points, balance_cents").eq("merchant_id", merchant_id).eq("customer_id", customer_id).execute()
    if not card_res.data:
        raise HTTPException(status_code=404, detail="Loyalty card not found")
    row = card_res.data[0]
    cust = supabase.table("customers").select("first_name").eq("id", customer_id).execute()
    customer_name = cust.data[0]["first_name"] if cust.data else None
    return {"points": row.get("points", 0), "balance": (row.get("balance_cents") or 0) / 100.0, "customer_name": customer_name}


@router.post("/cashback")
def cashback(req: CashbackRequest, merchant_id: str = Depends(get_current_merchant_id)):
    """Cashback earn/redeem. merchant_id comes from the session token."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    m_res = supabase.table("merchants").select("*").eq("id", merchant_id).execute()
    if not m_res.data:
        raise HTTPException(status_code=404, detail="Merchant not found")
    merchant = m_res.data[0]
    if (merchant.get("loyalty_type") or "points") != "cashback":
        raise HTTPException(status_code=400, detail="Ce commerçant n'utilise pas le cashback")
    rate = float(merchant.get("cashback_rate") or 0)

    # Money is stored and computed as integer cents.
    card_res = supabase.table("loyalty_cards").select("balance_cents").eq("merchant_id", merchant_id).eq("customer_id", req.customer_id).execute()
    if not card_res.data:
        raise HTTPException(status_code=404, detail="Loyalty card not found")
    balance_cents = int(card_res.data[0].get("balance_cents") or 0)
    amount_cents = round(req.amount * 100)

    earned_cents = redeemed_cents = None
    if req.operation == "earn":
        earned_cents = compute_cashback_earn_cents(amount_cents, rate)
        delta = earned_cents
    else:  # redeem
        if amount_cents > balance_cents:
            raise HTTPException(status_code=400, detail=f"Cagnotte insuffisante (solde : {balance_cents / 100:.2f} €)")
        redeemed_cents = amount_cents
        delta = -redeemed_cents

    # Atomic balance update (prevents double-spend on concurrent redeems).
    new_cents = None
    try:
        rpc_res = supabase.rpc("apply_cashback", {
            "p_merchant_id": merchant_id,
            "p_customer_id": req.customer_id,
            "p_delta_cents": delta,
        }).execute()
        if rpc_res.data:
            new_cents = rpc_res.data[0]["new_balance"]
        elif req.operation == "redeem":
            # The non-negative guard refused: the balance changed concurrently.
            raise HTTPException(status_code=409, detail="Cagnotte modifiée entre-temps, réessayez.")
    except HTTPException:
        raise
    except Exception as e:
        print(f"apply_cashback RPC unavailable, using fallback: {e}")

    if new_cents is None:
        # Non-atomic fallback (used only until the SQL migration is applied).
        new_cents = balance_cents + delta
        supabase.table("loyalty_cards").update({"balance_cents": new_cents}).eq("merchant_id", merchant_id).eq("customer_id", req.customer_id).execute()

    supabase.table("scan_logs").insert({
        "merchant_id": merchant_id,
        "customer_id": req.customer_id,
        "action_type": "CASHBACK_EARN" if req.operation == "earn" else "CASHBACK_REDEEM",
        "points_added": 0
    }).execute()

    # Convert back to euros only at the API/display boundary.
    new_balance = new_cents / 100.0
    earned = earned_cents / 100.0 if earned_cents is not None else None
    redeemed = redeemed_cents / 100.0 if redeemed_cents is not None else None

    label = merchant.get("points_label") or "Cagnotte"
    try:
        wallet_service.update_cashback(req.customer_id, new_balance, label, earned=earned, redeemed=redeemed)
    except Exception as e:
        print(f"Warning: cashback wallet update failed: {e}")

    return {"status": "success", "balance": new_balance, "earned": earned, "redeemed": redeemed}
