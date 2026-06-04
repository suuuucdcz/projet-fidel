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

    def generate_jwt_url(self, customer_id: str, merchant_id: str, points: int, merchant_name: str, threshold: int, reward_desc: str, first_name: str, color_hex: str, logo_url: str, hero_url: str, program_name: str = "", points_label: str = "", phone: str = "", website: str = "", loyalty_type: str = "points", balance: float = 0.0) -> str:
        """
        Generates a JWT link that the user clicks to add the card to Google Wallet.
        """
        template_path = os.path.join(os.path.dirname(__file__), "wallet_template.json")
        with open(template_path, "r", encoding="utf-8") as f:
            template = json.load(f)

        object_id = f"{self.issuer_id}.{customer_id}"
        class_id = f"{self.issuer_id}.class_{merchant_id}"
        
        loyalty_object = template["loyaltyObject"]
        loyalty_class = template["loyaltyClass"]

        # Customize class based on merchant
        loyalty_class["id"] = class_id
        loyalty_class["issuerName"] = merchant_name
        loyalty_class["programName"] = program_name or merchant_name
        if color_hex:
            loyalty_class["hexBackgroundColor"] = color_hex
        if logo_url:
            loyalty_class["programLogo"]["sourceUri"]["uri"] = logo_url
        # Hero banner is optional: only show it when the merchant set one (no random default).
        if hero_url:
            loyalty_class["heroImage"] = {"sourceUri": {"uri": hero_url}}
        else:
            loyalty_class.pop("heroImage", None)

        # Contact links shown on the card (phone / website)
        links = []
        if phone:
            links.append({"uri": f"tel:{phone}", "description": "Téléphone", "id": "phone"})
        if website:
            uri = website if website.startswith("http") else f"https://{website}"
            links.append({"uri": uri, "description": "Site web", "id": "website"})
        if links:
            loyalty_class["linksModuleData"] = {"uris": links}
        else:
            loyalty_class.pop("linksModuleData", None)

        # Customize object for customer
        loyalty_object["id"] = object_id
        loyalty_object["classId"] = class_id
        loyalty_object["barcode"]["value"] = customer_id

        if loyalty_type == "cashback":
            # Show a euro balance ("cagnotte") instead of integer points.
            loyalty_object["loyaltyPoints"]["label"] = points_label or "Cagnotte"
            loyalty_object["loyaltyPoints"]["balance"] = {"string": self._format_eur(balance)}
            objective = {
                "id": "points_info",
                "header": "Votre cagnotte fidélité",
                "body": f"{self._format_eur(balance)} à utiliser lors de vos prochains achats."
            }
        else:
            loyalty_object["loyaltyPoints"]["balance"] = {"int": points}
            if points_label:
                loyalty_object["loyaltyPoints"]["label"] = points_label
            objective = {
                "id": "points_info",
                "header": f"Objectif: {reward_desc}",
                "body": f"Plus que {max(threshold - points, 0)} points avant votre récompense !"
            }

        # Add personalized greeting and rules
        loyalty_object["textModulesData"] = [
            objective,
            {
                "id": "customer_greeting",
                "header": "Titulaire de la carte",
                "body": first_name
            }
        ]

        payload = {
            "iss": self.credentials.service_account_email if self.credentials else "dummy@email.com",
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(time.time()),
            "payload": {
                "loyaltyClasses": [loyalty_class],
                "loyaltyObjects": [loyalty_object]
            }
        }
        
        if self.private_key:
             token = jwt.encode(payload, self.private_key, algorithm="RS256")
        else:
             token = "DUMMY_TOKEN"
             
        return f"https://pay.google.com/gp/v/save/{token}"

    def update_class(self, merchant_id: str, merchant_name: str, program_name: str = "", color_hex: str = "", logo_url: str = "", hero_url: str = "", phone: str = "", website: str = ""):
        """PATCH the merchant's Wallet class so design changes (name, logo, banner, colour,
        links) reflect on ALL cards already saved by customers — not just new ones."""
        class_id = f"{self.issuer_id}.class_{merchant_id}"
        url = f"{self.base_url}/loyaltyClass/{class_id}"

        patch = {
            "issuerName": merchant_name,
            "programName": program_name or merchant_name,
        }
        if color_hex:
            patch["hexBackgroundColor"] = color_hex
        if logo_url:
            patch["programLogo"] = {"sourceUri": {"uri": logo_url}}
        if hero_url:
            patch["heroImage"] = {"sourceUri": {"uri": hero_url}}

        links = []
        if phone:
            links.append({"uri": f"tel:{phone}", "description": "Téléphone", "id": "phone"})
        if website:
            uri = website if website.startswith("http") else f"https://{website}"
            links.append({"uri": uri, "description": "Site web", "id": "website"})
        if links:
            patch["linksModuleData"] = {"uris": links}

        headers = self._get_auth_headers()
        response = requests.patch(url, headers=headers, json=patch)
        if response.status_code == 404:
            # No class yet (no card generated for this merchant) -> nothing to update;
            # it will be created with these values on the first card.
            print(f"Wallet class {class_id} not found yet; nothing to sync.")
            return None
        if response.status_code != 200:
            print(f"Failed to update Wallet class: {response.text}")
        return response.json() if response.status_code == 200 else None

    def update_points(self, customer_id: str, new_points: int, threshold: int, reward_desc: str, reward_unlocked: bool = False):
        """
        Updates an existing LoyaltyObject in Google Wallet and triggers a notification.
        """
        object_id = f"{self.issuer_id}.{customer_id}"
        url = f"{self.base_url}/loyaltyObject/{object_id}"
        
        remaining = max(threshold - new_points, 0)
        
        if reward_unlocked:
            body_text = f"Félicitations ! Vous avez débloqué : {reward_desc}. Votre carte repart à zéro !"
        else:
            body_text = f"Plus que {remaining} points avant : {reward_desc} !"

        patch_body = {
            "loyaltyPoints": {
                "balance": {
                    "int": new_points
                }
            },
            "textModulesData": [
                {
                    "id": "points_info",
                    "header": f"Objectif: {reward_desc}",
                    "body": body_text
                }
            ]
        }
        
        # If reward unlocked, optionally push a Message as well for better visibility
        if reward_unlocked:
            patch_body["messages"] = [{
                "header": "🎁 Récompense débloquée !",
                "body": f"Vous avez droit à : {reward_desc}. Montrez votre écran lors de votre prochain passage !",
                "id": str(uuid.uuid4()),
                # Push an actual notification when the reward unlocks (not just a silent message).
                "messageType": "TEXT_AND_NOTIFY"
            }]
            
        headers = self._get_auth_headers()
        url_with_notify = f"{url}?notifyOnUpdate=true"
        
        response = requests.patch(url_with_notify, headers=headers, json=patch_body)
        if response.status_code != 200:
            print(f"Failed to update Wallet Object: {response.text}")
        return response.json() if response.status_code == 200 else None

    def update_cashback(self, customer_id: str, new_balance: float, points_label: str = "", earned: float = None, redeemed: float = None):
        """Update a cashback card's euro balance and notify the customer."""
        object_id = f"{self.issuer_id}.{customer_id}"
        url = f"{self.base_url}/loyaltyObject/{object_id}"
        balance_str = self._format_eur(new_balance)

        if earned is not None:
            header = "💰 Cashback crédité !"
            msg_body = f"+{self._format_eur(earned)} sur votre cagnotte. Solde : {balance_str}."
        else:
            header = "🛍️ Cagnotte utilisée"
            msg_body = f"-{self._format_eur(redeemed)} utilisés. Solde restant : {balance_str}."

        patch_body = {
            "loyaltyPoints": {
                "label": points_label or "Cagnotte",
                "balance": {"string": balance_str}
            },
            "textModulesData": [{
                "id": "points_info",
                "header": "Votre cagnotte fidélité",
                "body": f"{balance_str} à utiliser lors de vos prochains achats."
            }],
            "messages": [{
                "header": header,
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
        url = f"{self.base_url}/loyaltyObject/{object_id}/addMessage"
        
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
