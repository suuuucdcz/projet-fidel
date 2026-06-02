-- Exécutez ce script dans l'onglet SQL Editor de Supabase pour mettre à jour vos tables existantes

ALTER TABLE customers
ADD COLUMN first_name VARCHAR(255),
ADD COLUMN last_name VARCHAR(255);

ALTER TABLE merchants
ADD COLUMN reward_threshold INTEGER DEFAULT 10,
ADD COLUMN reward_description VARCHAR(255) DEFAULT '-15% de réduction';
