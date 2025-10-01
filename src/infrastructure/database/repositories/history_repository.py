from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from src.domain.entities.edit_history import EditHistoryEntity

try:
    from supabase import Client
except Exception:  # pragma: no cover
    Client = object  # type: ignore

# module-level in-memory store for disabled mode
_MEM_HISTORY: dict[str, EditHistoryEntity] = {}


class HistoryRepository:
    def __init__(self, client: Optional[Client]) -> None:
        self.client = client
        self.disabled = os.getenv("SUPABASE_DISABLED", "0") == "1"

    def create(
        self, user_id: str, image_id: str, operation: str, params: dict[str, Any]
    ) -> EditHistoryEntity:
        now = datetime.now(timezone.utc)
        if self.disabled or self.client is None:
            hist_id = f"hist_{len(_MEM_HISTORY)+1}"
            entity = EditHistoryEntity(
                id=hist_id,
                user_id=user_id,
                image_id=image_id,
                operation=operation,
                params=params,
                created_at=now,
            )
            _MEM_HISTORY[entity.id] = entity
            return entity
        try:  # pragma: no cover - network
            data = {
                "user_id": user_id,
                "image_id": image_id,
                "operation": operation,
                "params": params,
                "created_at": now.isoformat(),
            }
            res = self.client.table("edit_history").insert(data).execute()
            row = res.data[0]
            return EditHistoryEntity(
                id=row["id"],
                user_id=row["user_id"],
                image_id=row["image_id"],
                operation=row["operation"],
                params=row.get("params", {}),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        except Exception as exc:
            raise RuntimeError(f"DB insert history failed: {exc}")

    def list_by_user(self, user_id: str) -> list[EditHistoryEntity]:
        if self.disabled or self.client is None:
            return [h for h in _MEM_HISTORY.values() if h.user_id == user_id]
        try:  # pragma: no cover - network
            res = self.client.table("edit_history").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            rows = res.data or []
            out: list[EditHistoryEntity] = []
            for row in rows:
                out.append(
                    EditHistoryEntity(
                        id=row["id"],
                        user_id=row["user_id"],
                        image_id=row["image_id"],
                        operation=row["operation"],
                        params=row.get("params", {}),
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
            return out
        except Exception as exc:
            raise RuntimeError(f"DB list history failed: {exc}")

    def get(self, hist_id: str) -> Optional[EditHistoryEntity]:
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
                operation=row["operation"],
                params=row.get("params", {}),
                created_at=datetime.fromisoformat(row["created_at"]),
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
