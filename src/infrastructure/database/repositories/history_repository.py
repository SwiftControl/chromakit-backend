from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from src.domain.entities.edit_history import EditHistoryEntity

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
            return EditHistoryEntity(
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
        except Exception as exc:
            raise RuntimeError(f"DB insert history failed: {exc}") from exc

    def list_by_user(self, user_id: str) -> list[EditHistoryEntity]:
        if self.disabled or self.client is None:
            return [h for h in _MEM_HISTORY.values() if h.user_id == user_id]
        try:  # pragma: no cover - network
            res = (
                self.client.table("edit_history")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
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
            raise RuntimeError(f"DB list history failed: {exc}") from exc

    def get(self, hist_id: str) -> EditHistoryEntity | None:
        if self.disabled or self.client is None:
            return _MEM_HISTORY.get(hist_id)
        try:  # pragma: no cover - network
            res = self.client.table("edit_history").select("*").eq("id", hist_id).single().execute()
            row = res.data
            if not row:
                return None
            return EditHistoryEntity(
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
        except Exception:
            return None

    def delete_by_image(self, image_id: str) -> int:
        if self.disabled or self.client is None:
            ids = [k for k, v in _MEM_HISTORY.items() if v.image_id == image_id]
            for k in ids:
                _MEM_HISTORY.pop(k, None)
            return len(ids)
        try:  # pragma: no cover - network
            self.client.table("edit_history").delete().eq("image_id", image_id).execute()
            return 0
        except Exception:
            return 0

    def delete(self, hist_id: str) -> bool:
        if self.disabled or self.client is None:
            return _MEM_HISTORY.pop(hist_id, None) is not None
        try:  # pragma: no cover - network
            self.client.table("edit_history").delete().eq("id", hist_id).execute()
            return True
        except Exception:
            return False

    def list_by_root_image(self, root_image_id: str, user_id: str) -> list[EditHistoryEntity]:
        """Get all edit history entries for a root image and its versions."""
        if self.disabled or self.client is None:
            return [
                h
                for h in _MEM_HISTORY.values()
                if h.user_id == user_id and h.root_image_id == root_image_id
            ]
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
