"""Shared FastAPI dependencies (device-token auth)."""

from anyio import to_thread
from fastapi import Depends, Header, HTTPException

from app.core.rbac import Principal
from app.services.auth_service import auth_service


async def get_current_user(authorization: str | None = Header(default=None)) -> Principal:
    """Resolve the bearer device token to a Principal; 401 when missing/invalid."""
    scheme = "Bearer "
    if not authorization or not authorization.startswith(scheme):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization[len(scheme):].strip()
    principal = await to_thread.run_sync(auth_service.resolve_principal, token)
    if principal is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return principal


CurrentUser = Depends(get_current_user)


def get_conversation_id(x_conversation_id: str | None = Header(default=None)) -> str | None:
    return x_conversation_id


ConversationIdDep = Depends(get_conversation_id)
