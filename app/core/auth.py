from fastapi import Header, HTTPException

from app.core.config import settings


def require_api_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    if not settings.api_key:
        return

    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()

    if x_api_key == settings.api_key or bearer == settings.api_key:
        return

    raise HTTPException(status_code=401, detail="invalid or missing API key")
