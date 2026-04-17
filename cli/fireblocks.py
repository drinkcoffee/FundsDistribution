"""Fireblocks REST API client for fundsdist."""

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass

import jwt
import requests

FIREBLOCKS_BASE_URL = "https://api.fireblocks.io"


@dataclass
class TransactionResponse:
    transaction_id: str
    status: str


class FireblocksClient:
    def __init__(self, api_key: str, private_key: str):
        self._api_key = api_key
        self._private_key = private_key

    @classmethod
    def from_env(cls) -> "FireblocksClient":
        """Construct from FIREBLOCKS_API_KEY and FIREBLOCKS_PRIVATE_KEY_PATH env vars."""
        api_key = os.environ.get("FIREBLOCKS_API_KEY")
        if not api_key:
            raise EnvironmentError("FIREBLOCKS_API_KEY environment variable is not set.")

        key_path = os.environ.get("FIREBLOCKS_PRIVATE_KEY_PATH")
        if not key_path:
            raise EnvironmentError("FIREBLOCKS_PRIVATE_KEY_PATH environment variable is not set.")

        try:
            private_key = open(key_path).read()
        except OSError as exc:
            raise EnvironmentError(f"Could not read private key from {key_path}: {exc}") from exc

        return cls(api_key=api_key, private_key=private_key)

    def _make_jwt(self, path: str, body: str) -> str:
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        now = int(time.time())
        payload = {
            "uri": path,
            "nonce": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 30,
            "sub": self._api_key,
            "bodyHash": body_hash,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def _post(self, path: str, body: dict) -> dict:
        body_json = json.dumps(body)
        token = self._make_jwt(path, body_json)
        headers = {
            "X-API-Key": self._api_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            f"{FIREBLOCKS_BASE_URL}{path}",
            headers=headers,
            data=body_json,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def submit_contract_call(
        self,
        vault_id: str,
        asset_id: str,
        to_address: str,
        calldata: str,
        note: str,
    ) -> TransactionResponse:
        """Submit a contract call transaction request to Fireblocks."""
        body = {
            "operation": "CONTRACT_CALL",
            "source": {
                "type": "VAULT_ACCOUNT",
                "id": vault_id,
            },
            "destination": {
                "type": "ONE_TIME_ADDRESS",
                "oneTimeAddress": {"address": to_address},
            },
            "assetId": asset_id,
            "amount": "0",
            "note": note,
            "extraParameters": {
                "contractCallData": calldata,
            },
        }
        result = self._post("/v1/transactions", body)
        return TransactionResponse(
            transaction_id=result["id"],
            status=result["status"],
        )
