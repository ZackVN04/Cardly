from datetime import datetime, timezone

from jose import ExpiredSignatureError, JWTError, jwt

from src.auth.constants import ALGORITHM, RESET_TOKEN_EXPIRE
from src.auth.exceptions import TokenExpired, TokenInvalid


def create_jwt(data: dict, expire_delta, secret: str) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + expire_delta
    payload.update({"exp": expire})
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def verify_jwt(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise TokenExpired()
    except JWTError:
        raise TokenInvalid()


def create_reset_token(email: str, secret: str) -> str:
    return create_jwt({"sub": email, "type": "reset"}, RESET_TOKEN_EXPIRE, secret)


def verify_reset_token(token: str, secret: str) -> str:
    payload = verify_jwt(token, secret)
    if payload.get("type") != "reset":
        raise TokenInvalid()
    return payload["sub"]
