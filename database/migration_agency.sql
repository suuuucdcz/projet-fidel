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
