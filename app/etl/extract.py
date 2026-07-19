from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import ETLSystem


class ExtractError(RuntimeError):
    pass


class SecretStore:
    def get(self, secret_name: str) -> str:
        value = os.getenv(secret_name, "").strip()
        if not value:
            raise ExtractError(f"missing secret value for {secret_name}")
        return value


@dataclass
class ExtractedBatch:
    system: str
    records: list[dict[str, Any]]


class IdentityAuthenticator:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    async def build_auth_headers(self, system: ETLSystem, secrets: SecretStore) -> dict[str, str]:
        provider = system.identity_provider
        if provider in {"okta", "entra_id"}:
            return await self._oauth_client_credentials_headers(system, secrets)
        if provider == "okta_ldap_agent":
            return self._ldap_agent_basic_headers(system, secrets)
        raise ExtractError(f"unsupported identity provider: {provider}")

    async def _oauth_client_credentials_headers(self, system: ETLSystem, secrets: SecretStore) -> dict[str, str]:
        if not system.token_url:
            raise ExtractError(f"token_url is required for {system.name}")
        if not system.client_id_secret or not system.client_secret_secret:
            raise ExtractError(f"client_id_secret and client_secret_secret are required for {system.name}")

        client_id = secrets.get(system.client_id_secret)
        client_secret = secrets.get(system.client_secret_secret)
        payload: dict[str, str] = {"grant_type": "client_credentials"}
        if system.scope:
            payload["scope"] = system.scope

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                system.token_url,
                data=payload,
                auth=(client_id, client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            body = response.json()

        access_token = str(body.get("access_token", "")).strip()
        if not access_token:
            raise ExtractError(f"access_token not found for {system.name}")
        return {"Authorization": f"Bearer {access_token}"}

    def _ldap_agent_basic_headers(self, system: ETLSystem, secrets: SecretStore) -> dict[str, str]:
        if not system.username_secret or not system.password_secret:
            raise ExtractError(f"username_secret and password_secret are required for {system.name}")

        username = secrets.get(system.username_secret)
        password = secrets.get(system.password_secret)
        credentials = json.dumps({"username": username, "password": password})
        return {"X-LDAP-Agent-Credentials": credentials}


class ExtractService:
    def __init__(self, timeout: float, secret_store: SecretStore | None = None) -> None:
        self.timeout = timeout
        self.secret_store = secret_store or SecretStore()
        self.authenticator = IdentityAuthenticator(timeout=timeout)

    async def run(self, system: ETLSystem) -> ExtractedBatch:
        auth_headers = await self.authenticator.build_auth_headers(system, self.secret_store)
        request_headers = {
            "Accept": "application/json",
            **auth_headers,
            **system.extra_headers,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                system.extract_method,
                system.extract_url,
                headers=request_headers,
            )
            response.raise_for_status()
            payload = response.json()

        records = payload.get(system.records_field, [])
        if not isinstance(records, list):
            raise ExtractError(f"records field '{system.records_field}' must be a list for {system.name}")

        normalized_records = [item for item in records if isinstance(item, dict)]
        return ExtractedBatch(system=system.name, records=normalized_records)
