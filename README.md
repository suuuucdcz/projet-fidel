# Fidélité Pro — Plateforme de cartes de fidélité (B2B2C)

Cartes de fidélité dématérialisées via **Google Wallet** (sans application mobile), opérées en
modèle B2B2C : une **agence** vend le service à des **commerçants**, qui fidélisent leurs **clients**.

## Architecture

| Composant | Stack | Hébergement | Dossier |
|-----------|-------|-------------|---------|
| API REST | Python / FastAPI | Render | `backend/` |
| Dashboard agence | HTML / Vanilla JS | Vercel | `dashboard-app/` |
| App commerçant (scanner) | HTML / Vanilla JS (PWA) | Vercel | `scanner-app/` |
| Inscription clients | HTML / Vanilla JS | Vercel | `public/` |
| Base de données | PostgreSQL | Supabase | `database/` |

Flux : le client scanne le QR du comptoir → s'inscrit sur `public/` → ajoute sa carte à Google
Wallet → le commerçant scanne le QR de la carte via `scanner-app/` → le backend incrémente les
points et pousse la mise à jour sur le Wallet du client.

## Backend — démarrage local

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows  (source venv/bin/activate sur macOS/Linux)
pip install -r requirements.txt
copy .env.example .env       # puis renseigner les valeurs
uvicorn main:app --reload
```

API sur http://localhost:8000 — docs interactives sur http://localhost:8000/docs.

### Variables d'environnement

Voir [`backend/.env.example`](backend/.env.example). En résumé :
`SUPABASE_URL`, `SUPABASE_KEY`, `GOOGLE_ISSUER_ID`, `GOOGLE_APPLICATION_CREDENTIALS`
(ou `GOOGLE_CREDENTIALS_JSON`), `ALLOWED_ORIGINS`, `ADMIN_TOKEN`, `SESSION_SECRET`
(+ `SESSION_TOKEN_DAYS`).

## Base de données

- Nouvelle base : exécuter [`database/schema.sql`](database/schema.sql) dans le SQL Editor Supabase.
- Base existante : exécuter [`database/migration_agency.sql`](database/migration_agency.sql) (idempotent).

## Frontends

Statique — il suffit de servir le dossier (`npx serve dashboard-app`, etc.) ou de le déployer sur
Vercel. L'URL de l'API est définie en haut de chaque fichier JS (`API_BASE_URL`).

## Sécurité

- Ne **jamais** committer `backend/.env` ni `backend/service_account.json` (déjà dans `.gitignore`).
- Si un secret a fuité (token GitHub, clé de service), le **révoquer et le régénérer** immédiatement.
- **Garde admin (agence)** : les endpoints `/dashboard/admin/*` (lister / créer / supprimer
  commerçants et clients, historiques, `update_offer`) exigent l'en-tête `X-Admin-Token` égal à la
  variable `ADMIN_TOKEN`. Le dashboard demande ce mot de passe une fois et le stocke. ⚠️ Si
  `ADMIN_TOKEN` est vide, la garde est **désactivée** (rétro-compatibilité) — définissez-la en prod.
- **Session commerçant (scanner)** : le login renvoie un **JWT** signé avec `SESSION_SECRET`. Le
  scanner l'envoie en `Authorization: Bearer ...` ; le backend dérive le `merchant_id` du token
  (jamais du corps). Un commerçant ne peut donc agir (`/cards/scan`, `/marketing/push`,
  `POST /merchants/settings`) que sur son propre compte. ⚠️ `SESSION_SECRET` doit être **fixe** en
  prod (sinon tous les commerçants sont déconnectés à chaque redémarrage).

## Limitations connues / à faire

- Rate-limiting sur `/merchants/login` et `/cards/generate` (anti brute-force PIN) à prévoir.
- Row Level Security (RLS) Supabase non activée (la clé serveur a tous les droits).
