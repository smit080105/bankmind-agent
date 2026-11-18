"""Microsoft Entra access-token validation for API authorization."""

from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from app.config import ENTRA_API_AUDIENCE, ENTRA_TENANT_ID


@lru_cache(maxsize=1)
def _jwks_client(tenant_id: str) -> PyJWKClient:
    return PyJWKClient(
        f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
        cache_jwk_set=True,
        lifespan=300,
        timeout=5,
    )


def validate_entra_access_token(token: str) -> dict[str, Any]:
    """Validate signature, issuer, audience, and time claims for an Entra v2 token."""
    signing_key = _jwks_client(ENTRA_TENANT_ID).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=ENTRA_API_AUDIENCE,
        issuer=f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0",
        options={"require": ["exp", "iss", "aud"]},
    )
