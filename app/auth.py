"""Clerk sign-in, verified here. No token = anonymous; a bad token = 401 (never silently anonymous).

The browser sends Clerk's session JWT as `Authorization: Bearer ...`. We check its signature
against the instance's public keys (JWKS), the issuer and the expiry. The publishable key is
public; its base64 body is the instance's Frontend API domain, which is all we need. The Clerk
secret key is not used.
"""

import base64
from functools import lru_cache

import jwt
from fastapi import HTTPException, Request

from app.config import get_settings


def clerk_domain(publishable_key: str) -> str:
    body = publishable_key.split("_", 2)[2]
    return base64.b64decode(body + "=" * (-len(body) % 4)).decode().rstrip("$")


@lru_cache
def _jwks(domain: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"https://{domain}/.well-known/jwks.json")


def signing_key(token: str, domain: str):
    return _jwks(domain).get_signing_key_from_jwt(token).key


def current_user(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Malformed Authorization header.")
    key = get_settings().clerk_publishable_key
    if not key:
        raise HTTPException(401, "Sign-in is not configured on this server.")
    domain = clerk_domain(key)
    try:
        claims = jwt.decode(
            token,
            signing_key(token, domain),
            algorithms=["RS256"],
            issuer=f"https://{domain}",
            leeway=10,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as e:  # bad signature, wrong issuer, expired, or JWKS unreachable
        raise HTTPException(401, "Your sign-in is invalid or has expired.") from e
    return claims["sub"]
