import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from routers import merchants, cards, marketing, admin

app = FastAPI(title="Loyalty Cards Agency Platform API")

# Allowed front-end origins. Override in production via the ALLOWED_ORIGINS env var
# (comma-separated). We do NOT use cookies, so allow_credentials stays False, which
# also lets us keep an explicit, safe allow-list instead of the invalid "*" + creds combo.
_default_origins = [
    "https://projet-fidel.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5500",
]
_env_origins = os.environ.get("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in _env_origins.split(",") if o.strip()] or _default_origins

# Also allow any *.vercel.app deployment by default, so the dashboard/scanner/signup
# previews keep working without listing every sub-domain. Override by setting
# ALLOWED_ORIGIN_REGEX (empty string disables the regex entirely).
allow_origin_regex = os.environ.get("ALLOWED_ORIGIN_REGEX", r"https://.*\.vercel\.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(merchants.router)
app.include_router(cards.router)
app.include_router(marketing.router)
app.include_router(admin.router)

@app.get("/")
def read_root():
    return {"message": "Agency Platform API is running"}
