from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
from app.config import settings
import jwt


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:  # securely hashes a password
    return password_hash.hash(password)


def verify_password(
    password: str, hashed_password: str
) -> bool:  # checks a password against its hash
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: str) -> str:  # issues a signed token for a user
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(
    token: str,
) -> dict:  # verifies the token signature and expiration
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp"]},
    )
