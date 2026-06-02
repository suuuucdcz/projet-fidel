-- Supabase SQL Schema for Loyalty Cards MVP

-- 1. Merchants Table
CREATE TABLE merchants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    reward_threshold INTEGER DEFAULT 10,
    reward_description VARCHAR(255) DEFAULT '-15% de réduction',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Customers Table
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Loyalty Cards Table
CREATE TABLE loyalty_cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    merchant_id UUID REFERENCES merchants(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    points INTEGER DEFAULT 0,
    google_wallet_object_id VARCHAR(255), -- ID of the generated wallet object
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(merchant_id, customer_id)
);

-- Insert a dummy merchant for testing
INSERT INTO merchants (name, email, password_hash) 
VALUES ('La Mie Câline - Test', 'test@lamiecaline.com', 'dummy_hash_for_now');

-- 4. Scan Logs Table (Historique)
CREATE TABLE scan_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    merchant_id UUID REFERENCES merchants(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    action_type VARCHAR(50), -- 'SCAN', 'REWARD', 'PUSH_CAMPAIGN'
    points_added INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
