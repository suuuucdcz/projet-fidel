-- Supabase SQL Schema — Loyalty Cards Agency Platform (B2B2C)
-- This file is the single source of truth for a fresh database.
-- For an EXISTING database, run database/migration_agency.sql instead.

-- Required for uuid_generate_v4(); enabled by default on Supabase but kept here
-- so a fresh self-hosted Postgres works too.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Merchants (B2B clients of the agency)
CREATE TABLE merchants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    reward_threshold INTEGER NOT NULL DEFAULT 10,
    reward_description VARCHAR(255) NOT NULL DEFAULT '-15% de réduction',
    -- Card design (injected into the Google Wallet class)
    color_hex VARCHAR(9) DEFAULT '#FF9800',
    logo_url TEXT DEFAULT '',
    hero_url TEXT DEFAULT '',
    -- Card customization
    program_name VARCHAR(100) DEFAULT '',
    points_label VARCHAR(30) DEFAULT 'Points',
    phone VARCHAR(30) DEFAULT '',
    website VARCHAR(300) DEFAULT '',
    -- Loyalty model: 'points', 'stamps', 'tiers' or 'cashback'. `tiers` holds [{threshold, reward}, ...].
    loyalty_type VARCHAR(20) DEFAULT 'points',
    tiers JSONB DEFAULT '[]'::jsonb,
    cashback_rate NUMERIC(5,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Customers (B2C end users — global identity across merchants)
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    pin_code VARCHAR(8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Loyalty Cards (link table: points of customer C at merchant M)
CREATE TABLE loyalty_cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    merchant_id UUID REFERENCES merchants(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    points INTEGER NOT NULL DEFAULT 0,
    balance_cents INTEGER NOT NULL DEFAULT 0, -- cashback "cagnotte", in integer cents
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(merchant_id, customer_id)
);

-- 4. Scan Logs (activity history)
CREATE TABLE scan_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    merchant_id UUID REFERENCES merchants(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    action_type VARCHAR(50), -- 'SCAN', 'REWARD', 'PUSH_CAMPAIGN'
    points_added INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Helpful indexes for the most frequent lookups.
CREATE INDEX idx_loyalty_cards_merchant ON loyalty_cards(merchant_id);
CREATE INDEX idx_scan_logs_merchant ON scan_logs(merchant_id, created_at DESC);

-- Atomic point increment (avoids the read-modify-write race in /cards/scan).
-- Returns the new balance and whether the reward threshold was reached (resets to 0).
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
