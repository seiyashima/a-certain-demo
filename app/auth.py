from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status
from jose import jwt
from jose.exceptions import JWTError

from app.config import Settings
from app.models import AuthContext


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")
    return token.strip()


def claims_to_auth_context(claims: dict[str, Any], settings: Settings) -> AuthContext:
    groups = claims.get(settings.okta_claim_groups, [])
    if isinstance(groups, str):
        groups = [item.strip().lower() for item in groups.split(",") if item.strip()]
    elif isinstance(groups, list):
        groups = [str(item).strip().lower() for item in groups if str(item).strip()]
    else:
        groups = []

    def normalized_claim(name: str) -> Optional[str]:
        value = claims.get(name)
        if value is None:
            return None
        text = str(value).strip().lower()
        return text or None

    return AuthContext(
        sub=normalized_claim(settings.okta_claim_sub),
        groups=groups,
        department=normalized_claim(settings.okta_claim_department),
        region=normalized_claim(settings.okta_claim_region),
        position=normalized_claim(settings.okta_claim_position),
        manager_id=normalized_claim(settings.okta_claim_manager_id),
    )


def _jwks_url(settings: Settings) -> str:
    if settings.okta_jwks_url:
        return settings.okta_jwks_url
    return f"{settings.okta_issuer.rstrip('/')}/v1/keys"


@lru_cache(maxsize=8)
def _jwks_keys(jwks_url: str) -> tuple[dict[str, Any], ...]:
    response = httpx.get(jwks_url, timeout=5.0)
    response.raise_for_status()
    payload = response.json()
    return tuple(payload.get("keys", []))


def _matching_jwk(token: str, settings: Settings) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    for key in _jwks_keys(_jwks_url(settings)):
        if key.get("kid") == kid:
            return key
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid Okta token: signing key not found")


def decode_okta_access_token(token: str, settings: Settings) -> AuthContext:
    try:
        claims = jwt.decode(
            token,
            _matching_jwk(token, settings),
            algorithms=["RS256"],
            audience=settings.okta_audience,
            issuer=settings.okta_issuer,
        )
    except (JWTError, httpx.HTTPError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid Okta token: {error}") from error

    return claims_to_auth_context(claims, settings)
