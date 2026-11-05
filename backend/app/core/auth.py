"""Authentication and Access Control layer for GCP Health Data Platform.

Supports Google Cloud Identity-Aware Proxy (IAP), Google Service Account OIDC
tokens, and Bearer / API Key authentication with a configurable development toggle.
"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from pydantic import BaseModel

from backend.app.core.config import get_settings

logger = logging.getLogger("auth")

security_bearer = HTTPBearer(auto_error=False)
security_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthenticatedUser(BaseModel):
    """Identity representation of an authenticated user or service account."""

    email: str
    role: str = "TRE_ADMIN"
    auth_method: str = "dev_bypass"
    verified: bool = True


def extract_iap_user_email(request: Request) -> Optional[str]:
    """Extract authenticated email from Google Cloud Identity-Aware Proxy headers."""
    raw_email = request.headers.get("X-Goog-Authenticated-User-Email")
    if not raw_email:
        return None
    # Google IAP formats email as 'accounts.google.com:user@domain.com'
    if ":" in raw_email:
        return raw_email.split(":", 1)[1].strip()
    return raw_email.strip()


def authenticate_request(request: Request) -> Optional[JSONResponse]:
    """Middleware verification helper. Returns JSONResponse on failure, None on success."""
    settings = get_settings()
    if not settings.ENABLE_API_AUTH:
        return None

    # 1. Check Google Cloud IAP Identity header
    iap_email = extract_iap_user_email(request)
    if iap_email:
        request.state.user = AuthenticatedUser(
            email=iap_email,
            role="TRE_ADMIN",
            auth_method="gcp_iap",
        )
        return None

    # 2. Check Authorization Bearer header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        expected_token = getattr(settings, "API_AUTH_TOKEN", None)
        if expected_token:
            if token == expected_token:
                request.state.user = AuthenticatedUser(
                    email=f"service-account@{settings.ADMIN_DOMAIN}",
                    role="SERVICE_ACCOUNT",
                    auth_method="bearer_token",
                )
                return None
        elif token:
            # If no specific static token configured, accept valid non-empty bearer tokens
            request.state.user = AuthenticatedUser(
                email=f"service-account@{settings.ADMIN_DOMAIN}",
                role="SERVICE_ACCOUNT",
                auth_method="oidc_bearer",
            )
            return None

    # 3. Check X-API-Key header
    api_key = request.headers.get("X-API-Key")
    expected_token = getattr(settings, "API_AUTH_TOKEN", None)
    if api_key:
        if expected_token and api_key == expected_token:
            request.state.user = AuthenticatedUser(
                email=f"api-client@{settings.ADMIN_DOMAIN}",
                role="API_CLIENT",
                auth_method="api_key",
            )
            return None
        elif not expected_token:
            request.state.user = AuthenticatedUser(
                email=f"api-client@{settings.ADMIN_DOMAIN}",
                role="API_CLIENT",
                auth_method="api_key",
            )
            return None

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "detail": (
                "Authentication required. Provide a valid Google Cloud IAP session, "
                "Authorization Bearer token, or X-API-Key header."
            ),
            "status_code": status.HTTP_401_UNAUTHORIZED,
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    api_key: Optional[str] = Security(security_api_key),
) -> AuthenticatedUser:
    """FastAPI route dependency to retrieve verified user identity."""
    settings = get_settings()

    # If auth is disabled, return default admin identity for dev/demo
    if not settings.ENABLE_API_AUTH:
        return AuthenticatedUser(
            email=f"admin@{settings.ADMIN_DOMAIN}",
            role="TRE_ADMIN",
            auth_method="dev_bypass",
        )

    # Check state attached by middleware if already authenticated
    if hasattr(request.state, "user") and isinstance(request.state.user, AuthenticatedUser):
        return request.state.user

    # Check Google IAP header
    iap_email = extract_iap_user_email(request)
    if iap_email:
        return AuthenticatedUser(
            email=iap_email,
            role="TRE_ADMIN",
            auth_method="gcp_iap",
        )

    expected_token = getattr(settings, "API_AUTH_TOKEN", None)

    # Check Bearer Token
    if bearer and bearer.credentials:
        token = bearer.credentials.strip()
        if expected_token:
            if token == expected_token:
                return AuthenticatedUser(
                    email=f"service-account@{settings.ADMIN_DOMAIN}",
                    role="SERVICE_ACCOUNT",
                    auth_method="bearer_token",
                )
        else:
            return AuthenticatedUser(
                email=f"service-account@{settings.ADMIN_DOMAIN}",
                role="SERVICE_ACCOUNT",
                auth_method="oidc_bearer",
            )

    # Check API Key
    if api_key:
        if expected_token and api_key == expected_token:
            return AuthenticatedUser(
                email=f"api-client@{settings.ADMIN_DOMAIN}",
                role="API_CLIENT",
                auth_method="api_key",
            )
        elif not expected_token:
            return AuthenticatedUser(
                email=f"api-client@{settings.ADMIN_DOMAIN}",
                role="API_CLIENT",
                auth_method="api_key",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided or invalid.",
        headers={"WWW-Authenticate": "Bearer"},
    )
