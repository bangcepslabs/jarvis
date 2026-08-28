from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)


async def require_client_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Authenticate client requests; tool authorization remains in the Core."""
    settings = get_settings()
    if not settings.auth_enabled:
        return
    if not settings.client_token or credentials is None or credentials.credentials != settings.client_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
