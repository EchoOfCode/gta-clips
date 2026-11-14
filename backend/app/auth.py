import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def require_api_key(
    header_key: str | None = Security(api_key_header),
    bearer_creds: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Enforces authentication for write and sensitive administrative operations.
    Accepts credentials via either 'X-API-Key' header or 'Authorization: Bearer <token>'.
    Does not rely solely on network-level Tailnet membership.
    """
    configured_key = settings.internal_api_key.strip()

    if not configured_key:
        # If no internal key is configured, reject write operations with 503
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative operations are disabled because INTERNAL_API_KEY is not configured.",
        )

    provided_key: str | None = None
    if header_key:
        provided_key = header_key.strip()
    elif bearer_creds and bearer_creds.credentials:
        provided_key = bearer_creds.credentials.strip()

    if not provided_key or not secrets.compare_digest(provided_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API credentials. Provide valid key in X-API-Key or Authorization Bearer header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_key
