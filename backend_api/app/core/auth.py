"""FastAPI auth dependencies and role checks."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_user_by_id
from app.core.security import AuthenticatedUser, decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)

ELEVATED_ROLES = {"supervisor", "safety_mgr", "admin"}


def _user_from_payload(payload: dict) -> AuthenticatedUser:
    user_id = int(payload["sub"])
    row = get_user_by_id(user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    role = row["role"]
    if role != payload.get("role"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token role is stale")
    return AuthenticatedUser(id=row["id"], email=row["email"], role=role)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return _user_from_payload(payload)


def require_roles(*roles: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    allowed = set(roles)

    async def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency


def can_view_all_sessions(user: AuthenticatedUser) -> bool:
    return user.role in ELEVATED_ROLES


def require_live_session_access(user: AuthenticatedUser, service) -> None:
    if user.role in ELEVATED_ROLES:
        return
    owner_id = getattr(service, "current_created_by_user_id", None)
    if owner_id is not None and owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another user's live session")


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        return None
    try:
        return _user_from_payload(payload)
    except HTTPException:
        return None


def token_from_query(request: Request) -> str | None:
    token = request.query_params.get("token")
    return token if token else None
