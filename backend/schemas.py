from pydantic import BaseModel

class LoginRequest(BaseModel):
    email: str
    password: str

class GenerateCardRequest(BaseModel):
    first_name: str
    last_name: str
    pin_code: str
    action: str = "signup"  # "signup" or "login"

class ScanRequest(BaseModel):
    customer_id: str
    merchant_id: str

class PushMessageRequest(BaseModel):
    merchant_id: str
    header: str
    body: str

class UpdateOfferRequest(BaseModel):
    merchant_id: str
    reward_threshold: int
    reward_description: str
    color_hex: str = "#FF9800"
    logo_url: str = ""
    hero_url: str = ""

class CreateMerchantRequest(BaseModel):
    name: str
    email: str
    password: str
