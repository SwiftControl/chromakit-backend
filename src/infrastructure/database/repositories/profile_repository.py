from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from src.domain.entities.profile import ProfileEntity

try:
    from supabase import Client
except Exception:  # pragma: no cover
    Client = object  # type: ignore


class ProfileRepository:
    def __init__(self, client: Optional[Client]) -> None:
        self.client = client
        self.disabled = os.getenv("SUPABASE_DISABLED", "0") == "1"
        self._mem: dict[str, ProfileEntity] = {}

    def upsert(self, user_id: str, email: Optional[str]) -> ProfileEntity:
        if self.disabled or self.client is None:
            entity = ProfileEntity(id=user_id, email=email, created_at=None, display_name=self._mem.get(user_id, ProfileEntity(user_id, email, None, None)).display_name)
            self._mem[user_id] = entity
            return entity
        try:  # pragma: no cover - network
            data = {"id": user_id, "email": email}
            self.client.table("profiles").upsert(data, on_conflict="id").execute()
            res = self.client.table("profiles").select("*").eq("id", user_id).single().execute()
            row = res.data
            return ProfileEntity(
                id=row["id"],
                email=row.get("email"),
                created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                display_name=row.get("display_name"),
            )
        except Exception as exc:
            raise RuntimeError(f"DB upsert profile failed: {exc}")

    def set_display_name(self, user_id: str, name: str) -> ProfileEntity:
        if self.disabled or self.client is None:
            current = self._mem.get(user_id) or ProfileEntity(id=user_id, email=None, created_at=None, display_name=None)
            updated = ProfileEntity(id=user_id, email=current.email, created_at=current.created_at, display_name=name)
            self._mem[user_id] = updated
            return updated
        try:  # pragma: no cover - network
            self.client.table("profiles").update({"display_name": name}).eq("id", user_id).execute()
            res = self.client.table("profiles").select("*").eq("id", user_id).single().execute()
            row = res.data
            return ProfileEntity(
                id=row["id"],
                email=row.get("email"),
                created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                display_name=row.get("display_name"),
            )
        except Exception as exc:
            raise RuntimeError(f"DB update profile failed: {exc}")
