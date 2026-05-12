from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.exceptions import TokenInvalid
from src.auth.utils import verify_jwt
from src.core.config import settings

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if credentials is None:
        raise TokenInvalid()
    payload = verify_jwt(credentials.credentials, settings.JWT_SECRET)
    user_id = payload.get("sub")
    if not user_id:
        raise TokenInvalid()
    return {"_id": user_id}


require_auth = Depends(get_current_user)
