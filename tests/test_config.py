import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_parse_provider_hosts() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        allowed_provider_hosts="docs.example.com,tickets.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            },
            {
                "name": "tickets",
                "base_url": "https://tickets.example.com",
                "bearer_token": "tickets-token",
            },
        ],
    )

    assert settings.allowed_provider_hosts == ["docs.example.com", "tickets.example.com"]
    assert [provider.name for provider in settings.providers] == ["docs", "tickets"]


def test_settings_rejects_provider_outside_allowlist() -> None:
    with pytest.raises(ValidationError, match="not in SEARCH_APP_ALLOWED_PROVIDER_HOSTS"):
        Settings(
            api_key="1234567890abcdef",
            allowed_provider_hosts="docs.example.com",
            providers=[
                {
                    "name": "docs",
                    "base_url": "https://tickets.example.com",
                    "bearer_token": "docs-token",
                }
            ],
        )
