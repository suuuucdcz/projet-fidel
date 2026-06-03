from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from routers import merchants, cards, marketing, admin

app = FastAPI(title="Loyalty Cards Agency Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
