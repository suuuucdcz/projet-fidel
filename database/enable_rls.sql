-- ============================================================================
-- Row Level Security (RLS) — protège la base si la clé Supabase venait à fuiter.
-- ============================================================================
--
-- ⚠️ PRÉREQUIS OBLIGATOIRE : le backend (variable SUPABASE_KEY sur Render) doit
-- utiliser la clé **service_role** (et NON la clé anon).
--   • service_role  -> CONTOURNE la RLS  -> le backend continue de tout faire ✅
--   • anon          -> RESPECTE la RLS   -> sans policy, le backend serait BLOQUÉ ❌
--
-- Comment vérifier quelle clé tu utilises :
--   Supabase → Settings → API. La clé "service_role" est marquée "secret".
--   Compare-la à la valeur de SUPABASE_KEY sur Render. Elles doivent correspondre.
--   (Astuce : colle la clé sur https://jwt.io et regarde le champ "role".)
--
-- Si tu utilises la clé service_role : exécute ce script.
-- Si tu utilises la clé anon : remplace d'abord SUPABASE_KEY par la service_role
-- sur Render, redéploie, vérifie que l'app marche, PUIS exécute ce script.
--
-- En cas de problème, rollback (voir tout en bas).
-- ============================================================================

ALTER TABLE merchants     ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers     ENABLE ROW LEVEL SECURITY;
ALTER TABLE loyalty_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_logs     ENABLE ROW LEVEL SECURITY;

-- Aucune policy n'est créée volontairement : par défaut, RLS = "deny all" pour les
-- rôles anon / authenticated. Le rôle service_role (utilisé par le backend) ignore
-- la RLS et garde donc un accès complet. Résultat : si la clé anon ou l'URL fuite,
-- personne ne peut lire/écrire les tables directement via l'API PostgREST.

-- ----------------------------------------------------------------------------
-- ROLLBACK (si jamais l'app casse après activation) :
--   ALTER TABLE merchants     DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE customers     DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE loyalty_cards DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE scan_logs     DISABLE ROW LEVEL SECURITY;
-- ----------------------------------------------------------------------------
