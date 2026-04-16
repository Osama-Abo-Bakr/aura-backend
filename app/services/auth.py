"""Supabase Auth service — wraps the Supabase Auth REST API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx
import structlog
from fastapi import HTTPException, status
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: Literal["bearer"] = "bearer"


class AuthServiceError(HTTPException):
    pass


class DuplicateEmailError(AuthServiceError):
    def __init__(self, detail: str = "Email already registered."):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidCredentialsError(AuthServiceError):
    def __init__(self, detail: str = "Invalid email or password."):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class InvalidRefreshTokenError(AuthServiceError):
    def __init__(self, detail: str = "Invalid or expired refresh token."):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class AuthService:
    BASE_URL = f"{settings.SUPABASE_URL}/auth/v1"

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=10.0)

    def _post(self, path: str, data: dict, extra_headers: dict | None = None) -> httpx.Response:
        """Post to Supabase Auth API with retry and timeout. Converts transport errors to 503."""
        try:
            return self._post_with_retry(path, data, extra_headers)
        except httpx.TransportError:
            raise AuthServiceError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable. Please try again.",
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    def _post_with_retry(self, path: str, data: dict, extra_headers: dict | None = None) -> httpx.Response:
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            **(extra_headers or {}),
        }
        resp = self._client.post(f"{self.BASE_URL}{path}", json=data, headers=headers)
        return resp

    def signup(self, email: str, password: str, full_name: str) -> dict:
        """Register a new user via Supabase Auth."""
        resp = self._post("/signup", {
            "email": email,
            "password": password,
            "data": {"full_name": full_name},
        })
        if resp.status_code == 400:
            body = resp.json()
            if "Email already registered" in body.get("msg", ""):
                raise DuplicateEmailError()
            raise DuplicateEmailError(detail=body.get("msg", "Registration failed."))
        if resp.status_code != 200:
            raise DuplicateEmailError(detail=f"Unexpected error: {resp.status_code}")
        return resp.json()

    def signin(self, email: str, password: str) -> AuthTokens:
        """Authenticate user and return tokens."""
        resp = self._post("/token?grant_type=password", {"email": email, "password": password})
        if resp.status_code == 400 or resp.status_code == 422:
            raise InvalidCredentialsError()
        if resp.status_code != 200:
            raise InvalidCredentialsError(detail=f"Unexpected error: {resp.status_code}")
        data = resp.json()
        return AuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
        )

    def refresh_token(self, refresh_token: str) -> AuthTokens:
        """Exchange a refresh token for new tokens via Supabase Auth REST API."""
        resp = self._post("/token?grant_type=refresh_token", {"refresh_token": refresh_token})
        if resp.status_code == 401 or resp.status_code == 400:
            raise InvalidRefreshTokenError()
        if resp.status_code != 200:
            raise InvalidRefreshTokenError(detail=f"Unexpected error: {resp.status_code}")
        data = resp.json()
        return AuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
        )

    def signout(self, access_token: str) -> None:
        """Revoke the user's session in Supabase by calling /auth/v1/logout."""
        try:
            self._post("/logout", {}, extra_headers={"Authorization": f"Bearer {access_token}"})
        except httpx.TransportError:
            pass  # Signout is best-effort — don't block the user on network failures
        except AuthServiceError:
            logger.warning("signout_failed", exc_info=True)
