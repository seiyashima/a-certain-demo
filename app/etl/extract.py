from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import ETLSystem
from app.etl.mock_data import build_mock_access_token, get_mock_records, get_mock_secret


class ExtractError(RuntimeError):
    pass


class SecretStore:
    def __init__(
        self,
        use_secret_manager: bool = False,
        use_mock: bool = False,
        project_id: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.use_secret_manager = use_secret_manager
        self.use_mock = use_mock
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "").strip() or None
        self._client = client

    def get(self, secret_name: str) -> str:
        if self.use_mock:
            return self._get_from_mock(secret_name)

        if self.use_secret_manager:
            return self._get_from_secret_manager(secret_name)

        value = os.getenv(secret_name, "").strip()
        if not value:
            raise ExtractError(f"missing secret value for {secret_name}")
        return value

    def _get_from_mock(self, secret_name: str) -> str:
        try:
            return get_mock_secret(secret_name)
        except KeyError:
            value = os.getenv(secret_name, "").strip()
            if value:
                return value
            raise ExtractError(f"missing mock secret value for {secret_name}")

    def _get_from_secret_manager(self, secret_name: str) -> str:
        version_name = self._build_secret_version_name(secret_name)
        client = self._secret_manager_client()
        try:
            response = client.access_secret_version(name=version_name)
        except Exception as error:  # pragma: no cover - provider-specific errors
            raise ExtractError(f"failed to access secret manager value for {secret_name}: {error}") from error

        value = response.payload.data.decode("utf-8").strip()
        if not value:
            raise ExtractError(f"empty secret manager value for {secret_name}")
        return value

    def _build_secret_version_name(self, secret_name: str) -> str:
        if secret_name.startswith("projects/"):
            if "/versions/" in secret_name:
                return secret_name
            return f"{secret_name}/versions/latest"

        if not self.project_id:
            raise ExtractError("GOOGLE_CLOUD_PROJECT or SEARCH_APP_ETL_SECRET_MANAGER_PROJECT_ID is required")
        return f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"

    def _secret_manager_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from google.cloud import secretmanager  # type: ignore
        except Exception as error:  # pragma: no cover - import error is environment dependent
            raise ExtractError("google-cloud-secret-manager is required when ETL secret manager mode is enabled") from error

        self._client = secretmanager.SecretManagerServiceClient()
        return self._client


@dataclass
class ExtractedBatch:
    system: str
    records: list[dict[str, Any]]


class IdentityAuthenticator:
    def __init__(self, timeout: float, use_mock: bool = False) -> None:
        self.timeout = timeout
        self.use_mock = use_mock

    async def build_auth_headers(self, system: ETLSystem, secrets: SecretStore) -> dict[str, str]:
        provider = system.identity_provider
        if provider in {"okta", "entra_id"}:
            return await self._oauth_client_credentials_headers(system, secrets)
        if provider == "okta_ldap_agent":
            return self._ldap_agent_basic_headers(system, secrets)
        raise ExtractError(f"unsupported identity provider: {provider}")

    async def _oauth_client_credentials_headers(self, system: ETLSystem, secrets: SecretStore) -> dict[str, str]:
        if self.use_mock:
            access_token = build_mock_access_token(system.name, system.identity_provider)
            return {"Authorization": f"Bearer {access_token}"}

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
    def __init__(
        self,
        timeout: float,
        secret_store: SecretStore | None = None,
        use_secret_manager: bool = False,
        use_mock: bool = False,
        project_id: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.use_mock = use_mock
        self.secret_store = secret_store or SecretStore(
            use_secret_manager=use_secret_manager,
            use_mock=use_mock,
            project_id=project_id,
        )
        self.authenticator = IdentityAuthenticator(timeout=timeout, use_mock=use_mock)

    async def run(self, system: ETLSystem) -> ExtractedBatch:
        if self.use_mock:
            return ExtractedBatch(system=system.name, records=get_mock_records(system.name))

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
