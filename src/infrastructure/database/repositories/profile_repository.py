from __future__ import annotations

import os
from datetime import datetime

from src.domain.entities.profile import ProfileEntity
from src.infrastructure.database.postgres_client import get_postgres_client

try:
    from supabase import Client
except Exception:  # pragma: no cover
    Client = object  # type: ignore


class ProfileRepository:
    def __init__(self, client: Client | None) -> None:
        self.client = client
        self.disabled = os.getenv("SUPABASE_DISABLED", "0") == "1"
        self.use_local_db = os.getenv("USE_LOCAL_DB", "0") == "1"
        self.pg_client = get_postgres_client() if self.use_local_db else None
        self._mem: dict[str, ProfileEntity] = {}

    def _row_to_entity(self, row: dict) -> ProfileEntity:
        """Convert database row to ProfileEntity."""
        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        return ProfileEntity(
            id=row["id"],
            email=row.get("email"),
            created_at=created_at,
            display_name=row.get("display_name"),
        )

    def upsert(self, user_id: str, email: str | None) -> ProfileEntity:
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            try:
                query = """
                    INSERT INTO profiles (id, email, created_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                    RETURNING *
                """
                row = self.pg_client.execute_insert(query, (user_id, email))
                return self._row_to_entity(row)
            except Exception as exc:
                raise RuntimeError(f"PostgreSQL upsert profile failed: {exc}") from exc
        
        # In-memory mode
        if self.disabled or self.client is None:
            entity = ProfileEntity(
                id=user_id,
                email=email,
                created_at=None,
                display_name=self._mem.get(
                    user_id, ProfileEntity(user_id, email, None, None)
                ).display_name,
            )
            self._mem[user_id] = entity
            return entity
        
        # Supabase mode
        try:  # pragma: no cover - network
            data = {"id": user_id, "email": email}
            self.client.table("profiles").upsert(data, on_conflict="id").execute()
            res = self.client.table("profiles").select("*").eq("id", user_id).single().execute()
            row = res.data
            return self._row_to_entity(row)
        except Exception as exc:
            raise RuntimeError(f"DB upsert profile failed: {exc}") from exc

    def set_display_name(self, user_id: str, name: str) -> ProfileEntity:
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            try:
                query = """
                    UPDATE profiles SET display_name = %s WHERE id = %s
                    RETURNING *
                """
                row = self.pg_client.execute_insert(query, (name, user_id))
                return self._row_to_entity(row)
            except Exception as exc:
                raise RuntimeError(f"PostgreSQL update profile failed: {exc}") from exc
        
        # In-memory mode
        if self.disabled or self.client is None:
            current = self._mem.get(user_id) or ProfileEntity(
                id=user_id, email=None, created_at=None, display_name=None
            )
            updated = ProfileEntity(
                id=user_id, email=current.email, created_at=current.created_at, display_name=name
            )
            self._mem[user_id] = updated
            return updated
        
        # Supabase mode
        try:  # pragma: no cover - network
            self.client.table("profiles").update({"display_name": name}).eq("id", user_id).execute()
            res = self.client.table("profiles").select("*").eq("id", user_id).single().execute()
            row = res.data
            return self._row_to_entity(row)
        except Exception as exc:
            raise RuntimeError(f"DB update profile failed: {exc}") from exc
