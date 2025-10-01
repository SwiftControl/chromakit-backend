from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - env without supabase installed
    Client = Any  # type: ignore
    create_client = None  # type: ignore


@dataclass(slots=True)
class UserInfo:
    id: str
    email: str | None


class SupabaseAuthAdapter:
    """Small wrapper to validate Supabase access tokens.

    When SUPABASE_DISABLED=1, this returns a fake user for any token.
    """

    def __init__(self) -> None:
        self.disabled = os.getenv("SUPABASE_DISABLED", "0") == "1"
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")
        self._client: Client | None = None
        if not self.disabled and self.url and self.key and create_client is not None:
            self._client = create_client(self.url, self.key)

    def validate_token(self, token: str) -> UserInfo:
        if not token:
            raise ValueError("Missing access token")
        if self.disabled or not self._client:
            # Return a deterministic fake user based on token hash
            fake_id = f"fake-{abs(hash(token)) % (10**10)}"
            return UserInfo(id=fake_id, email=None)
        # Real validation via Supabase Auth API
        try:
            res = self._client.auth.get_user(token)  # type: ignore[attr-defined]
            user = res.user  # type: ignore[assignment]
            if not user:
                raise ValueError("Invalid access token")
            return UserInfo(id=user.id, email=user.email)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - network path
            raise ValueError(f"Invalid access token: {exc}") from exc


# Simple reusable singleton client getter for repositories/storage
_CLIENT_SINGLETON: Client | None = None


def get_supabase_client() -> Client | None:
    global _CLIENT_SINGLETON
    disabled = os.getenv("SUPABASE_DISABLED", "0") == "1"
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if disabled or create_client is None or not url or not key:
        return None
    if _CLIENT_SINGLETON is None:
        _CLIENT_SINGLETON = create_client(url, key)
    return _CLIENT_SINGLETON
