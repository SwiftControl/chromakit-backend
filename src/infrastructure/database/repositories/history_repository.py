from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from src.domain.entities.edit_history import EditHistoryEntity
from src.infrastructure.database.postgres_client import get_postgres_client

try:
    from supabase import Client
except Exception:  # pragma: no cover
    Client = object  # type: ignore

# module-level in-memory store for disabled mode
_MEM_HISTORY: dict[str, EditHistoryEntity] = {}


class HistoryRepository:
    def __init__(self, client: Client | None) -> None:
        self.client = client
        self.disabled = os.getenv("SUPABASE_DISABLED", "0") == "1"
        self.use_local_db = os.getenv("USE_LOCAL_DB", "0") == "1"
        self.pg_client = get_postgres_client() if self.use_local_db else None

    def _row_to_entity(self, row: dict) -> EditHistoryEntity:
        """Convert database row to EditHistoryEntity."""
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        # Handle JSONB parameters from PostgreSQL
        parameters = row.get("parameters", {})
        if isinstance(parameters, str):
            parameters = json.loads(parameters)
        
        return EditHistoryEntity(
            id=row["id"],
            user_id=row["user_id"],
            image_id=row["image_id"],
            operation_type=row["operation_type"],
            parameters=parameters,
            result_storage_path=row.get("result_storage_path"),
            created_at=created_at,
            source_image_id=row.get("source_image_id"),
            root_image_id=row.get("root_image_id"),
        )

    def create(
        self,
        user_id: str,
        image_id: str,
        operation_type: str,
        parameters: dict[str, Any],
        result_storage_path: str | None = None,
        source_image_id: str | None = None,
        root_image_id: str | None = None,
    ) -> EditHistoryEntity:
        now = datetime.now(UTC)
        
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            try:
                query = """
                    INSERT INTO edit_history (
                        user_id, image_id, operation_type, parameters,
                        result_storage_path, source_image_id, root_image_id, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """
                row = self.pg_client.execute_insert(
                    query,
                    (
                        user_id, image_id, operation_type, json.dumps(parameters),
                        result_storage_path, source_image_id, root_image_id, now
                    ),
                )
                return self._row_to_entity(row)
            except Exception as exc:
                raise RuntimeError(f"PostgreSQL insert history failed: {exc}") from exc
        
        # In-memory mode
        if self.disabled or self.client is None:
            hist_id = f"hist_{len(_MEM_HISTORY)+1}"
            entity = EditHistoryEntity(
                id=hist_id,
                user_id=user_id,
                image_id=image_id,
                operation_type=operation_type,
                parameters=parameters,
                result_storage_path=result_storage_path,
                created_at=now,
                source_image_id=source_image_id,
                root_image_id=root_image_id,
            )
            _MEM_HISTORY[entity.id] = entity
            return entity
        
        # Supabase mode
        try:  # pragma: no cover - network
            data = {
                "user_id": user_id,
                "image_id": image_id,
                "operation_type": operation_type,
                "parameters": parameters,
                "created_at": now.isoformat(),
            }
            if result_storage_path:
                data["result_storage_path"] = result_storage_path
            if source_image_id:
                data["source_image_id"] = source_image_id
            if root_image_id:
                data["root_image_id"] = root_image_id
            res = self.client.table("edit_history").insert(data).execute()
            row = res.data[0]
            return self._row_to_entity(row)
        except Exception as exc:
            raise RuntimeError(f"DB insert history failed: {exc}") from exc

    def list_by_user(self, user_id: str) -> list[EditHistoryEntity]:
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            query = """
                SELECT * FROM edit_history 
                WHERE user_id = %s 
                ORDER BY created_at DESC
            """
            rows = self.pg_client.execute_many(query, (user_id,))
            return [self._row_to_entity(row) for row in rows]
        
        # In-memory mode
        if self.disabled or self.client is None:
            return [h for h in _MEM_HISTORY.values() if h.user_id == user_id]
        
        # Supabase mode
        try:  # pragma: no cover - network
            res = (
                self.client.table("edit_history")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            rows = res.data or []
            return [self._row_to_entity(row) for row in rows]
        except Exception as exc:
            raise RuntimeError(f"DB list history failed: {exc}") from exc

    def get(self, hist_id: str) -> EditHistoryEntity | None:
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            query = "SELECT * FROM edit_history WHERE id = %s"
            row = self.pg_client.execute_one(query, (hist_id,))
            return self._row_to_entity(row) if row else None
        
        # In-memory mode
        if self.disabled or self.client is None:
            return _MEM_HISTORY.get(hist_id)
        
        # Supabase mode
        try:  # pragma: no cover - network
            res = self.client.table("edit_history").select("*").eq("id", hist_id).single().execute()
            row = res.data
            return self._row_to_entity(row) if row else None
        except Exception:
            return None

    def delete_by_image(self, image_id: str) -> int:
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            query = "DELETE FROM edit_history WHERE image_id = %s"
            return self.pg_client.execute_update(query, (image_id,))
        
        # In-memory mode
        if self.disabled or self.client is None:
            ids = [k for k, v in _MEM_HISTORY.items() if v.image_id == image_id]
            for k in ids:
                _MEM_HISTORY.pop(k, None)
            return len(ids)
        
        # Supabase mode
        try:  # pragma: no cover - network
            self.client.table("edit_history").delete().eq("image_id", image_id).execute()
            return 0
        except Exception:
            return 0

    def delete(self, hist_id: str) -> bool:
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            query = "DELETE FROM edit_history WHERE id = %s"
            affected = self.pg_client.execute_update(query, (hist_id,))
            return affected > 0
        
        # In-memory mode
        if self.disabled or self.client is None:
            return _MEM_HISTORY.pop(hist_id, None) is not None
        
        # Supabase mode
        try:  # pragma: no cover - network
            self.client.table("edit_history").delete().eq("id", hist_id).execute()
            return True
        except Exception:
            return False

    def list_by_root_image(self, root_image_id: str, user_id: str) -> list[EditHistoryEntity]:
        """Get all edit history entries for a root image and its versions."""
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            query = """
                SELECT * FROM edit_history 
                WHERE root_image_id = %s AND user_id = %s 
                ORDER BY created_at ASC
            """
            rows = self.pg_client.execute_many(query, (root_image_id, user_id))
            return [self._row_to_entity(row) for row in rows]
        
        # In-memory mode
        if self.disabled or self.client is None:
            return [
                h
                for h in _MEM_HISTORY.values()
                if h.user_id == user_id and h.root_image_id == root_image_id
            ]
        
        # Supabase mode
        try:  # pragma: no cover - network
            res = (
                self.client.table("edit_history")
                .select("*")
                .eq("root_image_id", root_image_id)
                .eq("user_id", user_id)
                .order("created_at", desc=False)
                .execute()
            )
            rows = res.data or []
            return [self._row_to_entity(row) for row in rows]
        except Exception as exc:
            raise RuntimeError(f"DB list history by root failed: {exc}") from exc

    def list_by_image(self, image_id: str) -> list[EditHistoryEntity]:
        """Get all edit history entries for a specific image (result)."""
        if self.disabled or self.client is None:
            return [h for h in _MEM_HISTORY.values() if h.image_id == image_id]
        try:  # pragma: no cover - network
            res = (
                self.client.table("edit_history")
                .select("*")
                .eq("image_id", image_id)
                .order("created_at", desc=False)
                .execute()
            )
            rows = res.data or []
            out: list[EditHistoryEntity] = []
            for row in rows:
                out.append(
                    EditHistoryEntity(
                        id=row["id"],
                        user_id=row["user_id"],
                        image_id=row["image_id"],
                        operation_type=row["operation_type"],
                        parameters=row.get("parameters", {}),
                        result_storage_path=row.get("result_storage_path"),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        source_image_id=row.get("source_image_id"),
                        root_image_id=row.get("root_image_id"),
                    )
                )
            return out
        except Exception as exc:
            raise RuntimeError(f"DB list history by image failed: {exc}") from exc
