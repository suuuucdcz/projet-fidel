import os
import json
import time
import uuid
import requests
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
import jwt

class GoogleWalletService:
    def __init__(self):
        self.issuer_id = os.environ.get("GOOGLE_ISSUER_ID", "3388000000023151997")
        self.credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
        self.base_url = "https://walletobjects.googleapis.com/walletobjects/v1"
        self.scopes = ["https://www.googleapis.com/auth/wallet_object.issuer"]
        self.credentials = None
        self._load_credentials()

    def _load_credentials(self):
        env_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if env_json:
            try:
                creds_info = json.loads(env_json)
                self.credentials = Credentials.from_service_account_info(
                    creds_info, scopes=self.scopes
                )
                self.private_key = creds_info.get("private_key", "")
                return
            except Exception as e:
                print(f"Failed to load credentials from ENV: {e}")

        if os.path.exists(self.credentials_path):
            self.credentials = Credentials.from_service_account_file(
                self.credentials_path, scopes=self.scopes
            )
            with open(self.credentials_path, 'r') as f:
                 self.private_key = json.load(f).get("private_key", "")
        else:
            print(f"WARNING: Google Wallet Service Account not found.")
            self.private_key = ""

    def _get_auth_headers(self):
        if not self.credentials:
            raise Exception("Credentials not loaded")
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return {
            "Authorization": f"Bearer {self.credentials.token}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def _format_eur(value) -> str:
        return f"{float(value or 0):.2f} €".replace(".", ",")

    @staticmethod
    def _ls(value: str):
        """Google Wallet LocalizedString."""
        return {"defaultValue": {"language": "fr", "value": value or ""}}

    def _object_design(self, merchant_name, program_name="", color_hex="", logo_url="", hero_url="", phone="", website=""):
        """Design fields shared by a generic object (generic passes carry design per-object)."""
        design = {
            "cardTitle": self._ls(program_name or merchant_name),
            "hexBackgroundColor": color_hex or "#FF9800",
        }
        if logo_url:
            design["logo"] = {"sourceUri": {"uri": logo_url}}
        if hero_url:
            design["heroImage"] = {"sourceUri": {"uri": hero_url}}

        links = []
        if phone:
            links.append({"uri": f"tel:{phone}", "description": "Téléphone", "id": "phone"})
        if website:
            uri = website if website.startswith("http") else f"https://{website}"
            links.append({"uri": uri, "description": "Site web", "id": "website"})
        if links:
            design["linksModuleData"] = {"uris": links}
        return design

    def generate_jwt_url(self, customer_id: str, merchant_id: str, points: int, merchant_name: str, threshold: int, reward_desc: str, first_name: str, color_hex: str, logo_url: str, hero_url: str, program_name: str = "", points_label: str = "", phone: str = "", website: str = "", loyalty_type: str = "points", balance: float = 0.0) -> str:
        """Generate a 'Save to Google Wallet' JWT link using a Generic pass (more design freedom)."""
        object_id = f"{self.issuer_id}.{customer_id}"
        class_id = f"{self.issuer_id}.class_{merchant_id}"

        if loyalty_type == "cashback":
            header_value = self._format_eur(balance)
            objective_body = f"{self._format_eur(balance)} à utiliser lors de vos prochains achats."
        else:
            label = points_label or "Points"
            header_value = f"{points} {label}"
            objective_body = f"Plus que {max(threshold - points, 0)} {label.lower()} avant : {reward_desc}"

        generic_object = {
            "id": object_id,
            "classId": class_id,
            "genericType": "GENERIC_LOYALTY_CARD",
            "header": self._ls(header_value),
            "subheader": self._ls(first_name),
            "barcode": {"type": "QR_CODE", "value": customer_id, "alternateText": ""},
            "textModulesData": [
                {"id": "objective", "header": "Objectif", "body": objective_body},
            ],
        }
        generic_object.update(self._object_design(merchant_name, program_name, color_hex, logo_url, hero_url, phone, website))

        # Generic classes are minimal; the design lives on the object.
        generic_class = {"id": class_id}

        payload = {
            "iss": self.credentials.service_account_email if self.credentials else "dummy@email.com",
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(time.time()),
            "payload": {
                "genericClasses": [generic_class],
                "genericObjects": [generic_object]
            }
        }

        if self.private_key:
             token = jwt.encode(payload, self.private_key, algorithm="RS256")
        else:
             token = "DUMMY_TOKEN"

        return f"https://pay.google.com/gp/v/save/{token}"

    def update_object_design(self, customer_id: str, merchant_name: str, program_name: str = "", color_hex: str = "", logo_url: str = "", hero_url: str = "", phone: str = "", website: str = ""):
        """PATCH one generic object's design. Returns a diagnostic dict {ok,status,error}.

        Generic passes store design per-object, so propagating a merchant's design change
        means calling this for each of the merchant's cards (see admin.update_offer)."""
        object_id = f"{self.issuer_id}.{customer_id}"
        url = f"{self.base_url}/genericObject/{object_id}"
        patch = self._object_design(merchant_name, program_name, color_hex, logo_url, hero_url, phone, website)
        try:
            headers = self._get_auth_headers()
            response = requests.patch(url, headers=headers, json=patch)
        except Exception as e:
            return {"ok": False, "status": 0, "error": f"{type(e).__name__}: {e}"[:300]}
        if response.status_code == 200:
            return {"ok": True, "status": 200, "error": None}
        return {"ok": False, "status": response.status_code, "error": response.text[:300]}

    def update_points(self, customer_id: str, new_points: int, threshold: int, reward_desc: str, reward_unlocked: bool = False, points_label: str = "Points"):
        """Update a generic object's points header/objective and notify the customer."""
        object_id = f"{self.issuer_id}.{customer_id}"
        url = f"{self.base_url}/genericObject/{object_id}"
        label = points_label or "Points"
        remaining = max(threshold - new_points, 0)

        if reward_unlocked:
            body_text = f"Félicitations ! Vous avez débloqué : {reward_desc}. Votre carte repart à zéro !"
        else:
            body_text = f"Plus que {remaining} {label.lower()} avant : {reward_desc} !"

        patch_body = {
            "header": self._ls(f"{new_points} {label}"),
            "textModulesData": [
                {"id": "objective", "header": "Objectif", "body": body_text},
            ],
        }
        if reward_unlocked:
            patch_body["messages"] = [{
                "header": "🎁 Récompense débloquée !",
                "body": f"Vous avez droit à : {reward_desc}. Montrez votre écran lors de votre prochain passage !",
                "id": str(uuid.uuid4()),
                "messageType": "TEXT_AND_NOTIFY"
            }]

        headers = self._get_auth_headers()
        response = requests.patch(f"{url}?notifyOnUpdate=true", headers=headers, json=patch_body)
        if response.status_code != 200:
            print(f"Failed to update Wallet object: {response.text}")
        return response.json() if response.status_code == 200 else None

    def update_cashback(self, customer_id: str, new_balance: float, points_label: str = "", earned: float = None, redeemed: float = None):
        """Update a cashback generic object's euro balance and notify the customer."""
        object_id = f"{self.issuer_id}.{customer_id}"
        url = f"{self.base_url}/genericObject/{object_id}"
        balance_str = self._format_eur(new_balance)

        if earned is not None:
            mheader = "💰 Cashback crédité !"
            msg_body = f"+{self._format_eur(earned)} sur votre cagnotte. Solde : {balance_str}."
        else:
            mheader = "🛍️ Cagnotte utilisée"
            msg_body = f"-{self._format_eur(redeemed)} utilisés. Solde restant : {balance_str}."

        patch_body = {
            "header": self._ls(balance_str),
            "textModulesData": [
                {"id": "objective", "header": points_label or "Cagnotte",
                 "body": f"{balance_str} à utiliser lors de vos prochains achats."},
            ],
            "messages": [{
                "header": mheader,
                "body": msg_body,
                "id": str(uuid.uuid4()),
                "messageType": "TEXT_AND_NOTIFY"
            }]
        }
        headers = self._get_auth_headers()
        response = requests.patch(f"{url}?notifyOnUpdate=true", headers=headers, json=patch_body)
        if response.status_code != 200:
            print(f"Failed to update cashback: {response.text}")
        return response.json() if response.status_code == 200 else None

    def push_marketing_message(self, customer_id: str, header: str, body: str):
        object_id = f"{self.issuer_id}.{customer_id}"
        url = f"{self.base_url}/genericObject/{object_id}/addMessage"

        message_body = {
            "message": {
                "header": header,
                "body": body,
                "id": str(uuid.uuid4()),
                # TEXT_AND_NOTIFY pushes an Android notification AND adds the message to
                # the card. The default (TEXT) only adds it silently — no notification.
                "messageType": "TEXT_AND_NOTIFY"
            }
        }
        headers = self._get_auth_headers()
        response = requests.post(url, headers=headers, json=message_body)
        if response.status_code != 200:
            print(f"Failed to send marketing message: {response.text}")
            raise Exception(f"Google Wallet API Error {response.status_code}: {response.text}")
        return response.json()

wallet_service = GoogleWalletService()
