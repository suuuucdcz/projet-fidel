from typing import Optional

from pydantic import BaseModel, Field, field_validator

class LoginRequest(BaseModel):
    email: str
    password: str

class GenerateCardRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    pin_code: str
    action: str = "signup"  # "signup" or "login"

    @field_validator("first_name", "last_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("pin_code")
    @classmethod
    def _validate_pin(cls, v: str) -> str:
        v = v.strip()
        if not (v.isdigit() and len(v) == 4):
            raise ValueError("Le code PIN doit contenir exactement 4 chiffres.")
        return v

    @field_validator("action")
    @classmethod
    def _validate_action(cls, v: str) -> str:
        if v not in ("signup", "login"):
            raise ValueError("action must be 'signup' or 'login'")
        return v

class ScanRequest(BaseModel):
    # merchant_id is derived from the authenticated session token, not the body.
    customer_id: str

class PushMessageRequest(BaseModel):
    # merchant_id is derived from the authenticated session token, not the body.
    header: str
    body: str

class MerchantSettingsUpdate(BaseModel):
    # Self-service update used by the scanner app for the merchant's own offer.
    reward_threshold: int = Field(ge=1, le=1000)
    reward_description: str = Field(min_length=1, max_length=255)

class UpdateOfferRequest(BaseModel):
    merchant_id: str
    # All optional: a client that only edits the offer (e.g. the scanner app) must
    # not wipe the design fields it doesn't send. Only provided fields are updated.
    reward_threshold: Optional[int] = Field(default=None, ge=1, le=1000)
    reward_description: Optional[str] = Field(default=None, max_length=255)
    color_hex: Optional[str] = None
    logo_url: Optional[str] = None
    hero_url: Optional[str] = None

class CreateMerchantRequest(BaseModel):
    name: str
    email: str
    password: str
