"""Authentication and Access Control layer for GCP Health Data Platform.

Supports Google Cloud Identity-Aware Proxy (IAP) cryptographically verified JWT assertions,
Google Service Account OIDC tokens, and Bearer / API Key authentication with a configurable development toggle.
"""

import logging
import secrets
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
    """Helper to parse email from X-Goog-Authenticated-User-Email header."""
    raw_email = request.headers.get("X-Goog-Authenticated-User-Email")
    if not raw_email:
        return None
    if ":" in raw_email:
        return raw_email.split(":", 1)[1].strip()
    return raw_email.strip()


def verify_iap_jwt(request: Request) -> Optional[str]:
    """Verify cryptographically signed Google Cloud IAP JWT assertion and extract email.
    
    Strictly validates X-Goog-IAP-JWT-Assertion header using Google IAP public keys.
    Unverified raw identity headers such as X-Goog-Authenticated-User-Email are never
    accepted as an authentication mechanism in any environment.
    """
    settings = get_settings()
    iap_jwt = request.headers.get("X-Goog-IAP-JWT-Assertion")
    if not iap_jwt:
        return None

    audience = getattr(settings, "IAP_AUDIENCE", None)
    if settings.ENVIRONMENT != "development" and not audience:
        logger.error("IAP verification rejected: IAP_AUDIENCE must be configured in non-development environments.")
        return None

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
        decoded = id_token.verify_token(
            iap_jwt,
            google_requests.Request(),
            audience=audience,
            certs_url="https://www.gstatic.com/iap/verify/public_key-jwk",
        )
        email = decoded.get("email")
        if email:
            return email.strip()
    except Exception as e:
        logger.warning("IAP JWT cryptographic verification failed: %s", e)
        return None

    return None


def verify_oidc_token(token: str) -> Optional[str]:
    """Verify Google OIDC / ID token signature against Google public keys.
    
    Enforces audience verification (fails closed if OIDC_AUDIENCE is not configured).
    """
    settings = get_settings()
    audience = getattr(settings, "OIDC_AUDIENCE", None)
    if not audience:
        logger.warning("OIDC token verification rejected: OIDC_AUDIENCE is not configured.")
        return None

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        claim = id_token.verify_oauth2_token(token, google_requests.Request(), audience=audience)
        return claim.get("email")
    except Exception as e:
        logger.debug("OIDC token verification failed: %s", e)
        return None


def authenticate_request(request: Request) -> Optional[JSONResponse]:
    """Middleware verification helper. Returns JSONResponse on failure, None on success."""
    settings = get_settings()
    if not settings.ENABLE_API_AUTH:
        return None

    # 1. Check Google Cloud IAP cryptographically verified identity
    iap_email = verify_iap_jwt(request)
    if iap_email:
        request.state.user = AuthenticatedUser(
            email=iap_email,
            role="TRE_ADMIN",
            auth_method="gcp_iap",
            verified=True,
        )
        return None

    expected_token = getattr(settings, "API_AUTH_TOKEN", None)

    # 2. Check Authorization Bearer header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if expected_token:
            if secrets.compare_digest(token, expected_token):
                request.state.user = AuthenticatedUser(
                    email=f"service-account@{settings.ADMIN_DOMAIN}",
                    role="SERVICE_ACCOUNT",
                    auth_method="bearer_token",
                    verified=True,
                )
                return None
        elif token:
            # If static token is not set, attempt verifying Google OIDC token signature
            oidc_email = verify_oidc_token(token)
            if oidc_email:
                request.state.user = AuthenticatedUser(
                    email=oidc_email,
                    role="SERVICE_ACCOUNT",
                    auth_method="google_oidc",
                    verified=True,
                )
                return None

    # 3. Check X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key and expected_token:
        if secrets.compare_digest(api_key, expected_token):
            request.state.user = AuthenticatedUser(
                email=f"api-client@{settings.ADMIN_DOMAIN}",
                role="API_CLIENT",
                auth_method="api_key",
                verified=True,
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
            verified=True,
        )

    # Check state attached by middleware if already authenticated
    if hasattr(request.state, "user") and isinstance(request.state.user, AuthenticatedUser):
        return request.state.user

    # Check Google IAP cryptographically verified identity
    iap_email = verify_iap_jwt(request)
    if iap_email:
        return AuthenticatedUser(
            email=iap_email,
            role="TRE_ADMIN",
            auth_method="gcp_iap",
            verified=True,
        )

    expected_token = getattr(settings, "API_AUTH_TOKEN", None)

    # Check Bearer Token
    if bearer and bearer.credentials:
        token = bearer.credentials.strip()
        if expected_token:
            if secrets.compare_digest(token, expected_token):
                return AuthenticatedUser(
                    email=f"service-account@{settings.ADMIN_DOMAIN}",
                    role="SERVICE_ACCOUNT",
                    auth_method="bearer_token",
                    verified=True,
                )
        else:
            oidc_email = verify_oidc_token(token)
            if oidc_email:
                return AuthenticatedUser(
                    email=oidc_email,
                    role="SERVICE_ACCOUNT",
                    auth_method="google_oidc",
                    verified=True,
                )

    # Check API Key
    if api_key and expected_token:
        if secrets.compare_digest(api_key, expected_token):
            return AuthenticatedUser(
                email=f"api-client@{settings.ADMIN_DOMAIN}",
                role="API_CLIENT",
                auth_method="api_key",
                verified=True,
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided or invalid.",
        headers={"WWW-Authenticate": "Bearer"},
    )
