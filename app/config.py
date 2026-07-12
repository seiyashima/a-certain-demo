from __future__ import annotations

from functools import lru_cache
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SaaSProvider(BaseModel):
    name: str = Field(min_length=1)
    base_url: str
    search_path: str = "/search"
    bearer_token: str = Field(min_length=1)
    result_limit: int = Field(default=10, ge=1, le=50)

    @field_validator("base_url")
    @classmethod
    def validate_https_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("base_url must be a valid https URL")
        return value.rstrip("/")

    @field_validator("search_path")
    @classmethod
    def validate_search_path(cls, value: str) -> str:
        normalized = value if value.startswith("/") else f"/{value}"
        if "?" in normalized or "#" in normalized:
            raise ValueError("search_path must not include query string or fragment")
        return normalized


class ACLPolicy(BaseModel):
    principal: str = Field(min_length=1)
    allowed_providers: List[str] = Field(default_factory=list)
    allowed_groups: List[str] = Field(default_factory=list)
    allowed_departments: List[str] = Field(default_factory=list)
    allowed_regions: List[str] = Field(default_factory=list)
    allowed_positions: List[str] = Field(default_factory=list)
    require_manager: bool = False
    max_query_length: Optional[int] = Field(default=None, ge=1, le=500)
    max_results_per_provider: Optional[int] = Field(default=None, ge=1, le=50)

    @field_validator("principal")
    @classmethod
    def normalize_principal(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("principal must not be empty")
        return normalized

    @field_validator("allowed_providers", mode="before")
    @classmethod
    def split_allowed_providers(cls, value: str | List[str]) -> List[str]:
        if isinstance(value, list):
            return [item.strip().lower() for item in value if item.strip()]
        if not value:
            return []
        return [item.strip().lower() for item in value.split(",") if item.strip()]

    @field_validator("allowed_groups", "allowed_departments", "allowed_regions", "allowed_positions", mode="before")
    @classmethod
    def split_normalized_list(cls, value: str | List[str]) -> List[str]:
        if isinstance(value, list):
            return [item.strip().lower() for item in value if item.strip()]
        if not value:
            return []
        return [item.strip().lower() for item in value.split(",") if item.strip()]

    @field_validator("allowed_providers")
    @classmethod
    def require_non_empty_allowed_providers(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("allowed_providers must include at least one provider")
        return value


class Settings(BaseSettings):
    service_name: str = "federated-search-api"
    api_key: str = Field(min_length=16)
    okta_auth_enabled: bool = False
    okta_issuer: Optional[str] = None
    okta_audience: Optional[str] = None
    okta_jwks_url: Optional[str] = None
    okta_claim_sub: str = "sub"
    okta_claim_groups: str = "groups"
    okta_claim_department: str = "department"
    okta_claim_region: str = "region"
    okta_claim_position: str = "position"
    okta_claim_manager_id: str = "managerId"
    request_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    max_query_length: int = Field(default=120, ge=1, le=500)
    max_results_per_provider: int = Field(default=10, ge=1, le=50)
    allowed_provider_hosts: List[str] = Field(default_factory=list)
    providers: List[SaaSProvider] = Field(default_factory=list)
    acl_enabled: bool = False
    acl_policies: List[ACLPolicy] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_prefix="SEARCH_APP_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    @field_validator("allowed_provider_hosts", mode="before")
    @classmethod
    def split_hosts(cls, value: str | List[str]) -> List[str]:
        if isinstance(value, list):
            return [item.strip().lower() for item in value if item.strip()]
        if not value:
            return []
        return [item.strip().lower() for item in value.split(",") if item.strip()]

    @field_validator("providers")
    @classmethod
    def enforce_provider_hosts(cls, providers: List[SaaSProvider], info) -> List[SaaSProvider]:
        allowed_hosts = set(info.data.get("allowed_provider_hosts", []))
        provider_names: set[str] = set()
        for provider in providers:
            normalized_name = provider.name.strip().lower()
            if normalized_name in provider_names:
                raise ValueError(f"duplicate provider name: {provider.name}")
            provider_names.add(normalized_name)
            host = urlparse(provider.base_url).hostname or ""
            if allowed_hosts and host.lower() not in allowed_hosts:
                raise ValueError(f"provider host '{host}' is not in SEARCH_APP_ALLOWED_PROVIDER_HOSTS")
        return providers

    @model_validator(mode="after")
    def require_allowlist_when_providers_configured(self) -> "Settings":
        if self.providers and not self.allowed_provider_hosts:
            raise ValueError("SEARCH_APP_ALLOWED_PROVIDER_HOSTS is required when providers are configured")

        if self.okta_auth_enabled and (not self.okta_issuer or not self.okta_audience):
            raise ValueError("SEARCH_APP_OKTA_ISSUER and SEARCH_APP_OKTA_AUDIENCE are required when SEARCH_APP_OKTA_AUTH_ENABLED=true")

        provider_names = {provider.name.strip().lower() for provider in self.providers}
        acl_principals: set[str] = set()
        for policy in self.acl_policies:
            if policy.principal in acl_principals:
                raise ValueError(f"duplicate ACL principal: {policy.principal}")
            acl_principals.add(policy.principal)

            unknown_providers = sorted(set(policy.allowed_providers) - provider_names)
            if unknown_providers:
                raise ValueError(
                    f"ACL policy for '{policy.principal}' references unknown providers: {', '.join(unknown_providers)}"
                )

        if self.acl_enabled and not self.acl_policies:
            raise ValueError("SEARCH_APP_ACL_POLICIES is required when SEARCH_APP_ACL_ENABLED=true")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
