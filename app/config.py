from functools import lru_cache
from typing import List
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
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
        return value if value.startswith("/") else f"/{value}"


class Settings(BaseSettings):
    service_name: str = "federated-search-api"
    api_key: str = Field(min_length=16)
    request_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    max_query_length: int = Field(default=120, ge=1, le=500)
    max_results_per_provider: int = Field(default=10, ge=1, le=50)
    allowed_provider_hosts: List[str] = Field(default_factory=list)
    providers: List[SaaSProvider] = Field(default_factory=list)

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
        for provider in providers:
            host = urlparse(provider.base_url).hostname or ""
            if allowed_hosts and host.lower() not in allowed_hosts:
                raise ValueError(f"provider host '{host}' is not in SEARCH_APP_ALLOWED_PROVIDER_HOSTS")
        return providers


@lru_cache
def get_settings() -> Settings:
    return Settings()
