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


def test_settings_requires_allowlist_when_providers_exist() -> None:
    with pytest.raises(ValidationError, match="SEARCH_APP_ALLOWED_PROVIDER_HOSTS is required"):
        Settings(
            api_key="1234567890abcdef",
            providers=[
                {
                    "name": "docs",
                    "base_url": "https://docs.example.com",
                    "bearer_token": "docs-token",
                }
            ],
        )


def test_settings_rejects_duplicate_provider_names() -> None:
    with pytest.raises(ValidationError, match="duplicate provider name"):
        Settings(
            api_key="1234567890abcdef",
            allowed_provider_hosts="docs.example.com",
            providers=[
                {
                    "name": "Docs",
                    "base_url": "https://docs.example.com",
                    "bearer_token": "docs-token",
                },
                {
                    "name": "docs",
                    "base_url": "https://docs.example.com",
                    "bearer_token": "docs-token-2",
                },
            ],
        )


def test_settings_rejects_acl_policy_for_unknown_provider() -> None:
    with pytest.raises(ValidationError, match="references unknown providers"):
        Settings(
            api_key="1234567890abcdef",
            allowed_provider_hosts="docs.example.com",
            providers=[
                {
                    "name": "docs",
                    "base_url": "https://docs.example.com",
                    "bearer_token": "docs-token",
                }
            ],
            acl_enabled=True,
            acl_policies=[
                {
                    "principal": "web-client",
                    "allowed_providers": ["tickets"],
                }
            ],
        )


def test_settings_requires_acl_policies_when_acl_enabled() -> None:
    with pytest.raises(ValidationError, match="SEARCH_APP_ACL_POLICIES is required"):
        Settings(
            api_key="1234567890abcdef",
            allowed_provider_hosts="docs.example.com",
            providers=[
                {
                    "name": "docs",
                    "base_url": "https://docs.example.com",
                    "bearer_token": "docs-token",
                }
            ],
            acl_enabled=True,
            acl_policies=[],
        )


def test_settings_requires_okta_issuer_and_audience_when_okta_auth_enabled() -> None:
    with pytest.raises(ValidationError, match="SEARCH_APP_OKTA_ISSUER and SEARCH_APP_OKTA_AUDIENCE are required"):
        Settings(
            api_key="1234567890abcdef",
            okta_auth_enabled=True,
            allowed_provider_hosts="docs.example.com",
            providers=[
                {
                    "name": "docs",
                    "base_url": "https://docs.example.com",
                    "bearer_token": "docs-token",
                }
            ],
        )
