-- Run this in the Supabase SQL Editor to bring an EXISTING database up to date
-- with the current code. Safe to re-run (uses IF NOT EXISTS / OR REPLACE).

-- Customers: names + secret PIN
ALTER TABLE customers ADD COLUMN IF NOT EXISTS first_name VARCHAR(255);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_name  VARCHAR(255);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS pin_code   VARCHAR(8);

-- Merchants: reward rules + card design
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS reward_threshold   INTEGER DEFAULT 10;
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS reward_description VARCHAR(255) DEFAULT '-15% de réduction';
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS color_hex          VARCHAR(9) DEFAULT '#FF9800';
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS logo_url           TEXT DEFAULT '';
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS hero_url           TEXT DEFAULT '';

-- Card customization
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS program_name VARCHAR(100) DEFAULT '';
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS points_label VARCHAR(30) DEFAULT 'Points';
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS phone        VARCHAR(30) DEFAULT '';
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS website      VARCHAR(300) DEFAULT '';

-- Loyalty model
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS loyalty_type  VARCHAR(20) DEFAULT 'points';
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS tiers         JSONB DEFAULT '[]'::jsonb;
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS cashback_rate NUMERIC(5,2) DEFAULT 0;

-- Cashback balance ("cagnotte") per loyalty card — stored as integer cents.
ALTER TABLE loyalty_cards ADD COLUMN IF NOT EXISTS balance_cents INTEGER NOT NULL DEFAULT 0;

-- One-time migration from the old NUMERIC `balance` (euros) to integer cents, then drop it.
-- Safe to re-run: once `balance` is dropped, this block is skipped.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'loyalty_cards' AND column_name = 'balance'
    ) THEN
        UPDATE loyalty_cards SET balance_cents = ROUND(COALESCE(balance, 0) * 100) WHERE balance_cents = 0;
        ALTER TABLE loyalty_cards DROP COLUMN balance;
    END IF;
END $$;

-- Indexes for frequent lookups
CREATE INDEX IF NOT EXISTS idx_loyalty_cards_merchant ON loyalty_cards(merchant_id);
CREATE INDEX IF NOT EXISTS idx_scan_logs_merchant ON scan_logs(merchant_id, created_at DESC);

-- Atomic point increment (see schema.sql for details)
CREATE OR REPLACE FUNCTION increment_loyalty_points(p_merchant_id UUID, p_customer_id UUID)
RETURNS TABLE(new_points INTEGER, reward_triggered BOOLEAN) AS $$
DECLARE
    v_threshold INTEGER;
    v_points INTEGER;
BEGIN
    SELECT reward_threshold INTO v_threshold FROM merchants WHERE id = p_merchant_id;

    UPDATE loyalty_cards
       SET points = points + 1
     WHERE merchant_id = p_merchant_id AND customer_id = p_customer_id
     RETURNING points INTO v_points;

    IF v_points IS NULL THEN
        RAISE EXCEPTION 'Loyalty card not found';
    END IF;

    IF v_points >= v_threshold THEN
        UPDATE loyalty_cards SET points = 0
         WHERE merchant_id = p_merchant_id AND customer_id = p_customer_id;
        RETURN QUERY SELECT 0, TRUE;
    ELSE
        RETURN QUERY SELECT v_points, FALSE;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Atomic tier increment: +1 point, reset to 0 once the top tier threshold is reached.
-- Returns the post-reset balance plus the pre-reset value reached (so the app can tell
-- which tier reward fired). Avoids the read-modify-write race for tier cards.
CREATE OR REPLACE FUNCTION increment_tiers(p_merchant_id UUID, p_customer_id UUID, p_max_threshold INTEGER)
RETURNS TABLE(new_points INTEGER, reached INTEGER) AS $$
DECLARE
    v_points INTEGER;
BEGIN
    UPDATE loyalty_cards SET points = points + 1
     WHERE merchant_id = p_merchant_id AND customer_id = p_customer_id
     RETURNING points INTO v_points;

    IF v_points IS NULL THEN
        RETURN;  -- no card -> empty result
    END IF;

    IF v_points >= p_max_threshold THEN
        UPDATE loyalty_cards SET points = 0
         WHERE merchant_id = p_merchant_id AND customer_id = p_customer_id;
        RETURN QUERY SELECT 0, v_points;
    ELSE
        RETURN QUERY SELECT v_points, v_points;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Atomic cashback: add p_delta_cents (negative to redeem), refusing to go below 0.
-- Returns the new balance; empty result if the card is missing or the balance would go negative.
CREATE OR REPLACE FUNCTION apply_cashback(p_merchant_id UUID, p_customer_id UUID, p_delta_cents INTEGER)
RETURNS TABLE(new_balance INTEGER) AS $$
BEGIN
    RETURN QUERY
    UPDATE loyalty_cards
       SET balance_cents = balance_cents + p_delta_cents
     WHERE merchant_id = p_merchant_id AND customer_id = p_customer_id
       AND balance_cents + p_delta_cents >= 0
     RETURNING balance_cents;
END;
$$ LANGUAGE plpgsql;
