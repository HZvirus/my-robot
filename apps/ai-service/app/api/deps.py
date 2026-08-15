'''Shared FastAPI dependencies (device-token auth).'''

from anyio import to_thread
from fastapi import Depends, Header, HTTPException

from app.services.auth_service import auth_service


async def get_current_user(authorization: str | None = Header(default=None)) -> str:
    '''Resolve the bearer device token to a user id; 401 when missing or invalid.'''
    scheme = 'Bearer '
    if not authorization or not authorization.startswith(scheme):
        raise HTTPException(status_code=401, detail='missing bearer token')
    token = authorization[len(scheme):].strip()
    user_id = await to_thread.run_sync(auth_service.verify_token, token)
    if user_id is None:
        raise HTTPException(status_code=401, detail='invalid token')
    return user_id


CurrentUser = Depends(get_current_user)


def get_conversation_id(x_conversation_id: str | None = Header(default=None)) -> str | None:
    return x_conversation_id


ConversationIdDep = Depends(get_conversation_id)
