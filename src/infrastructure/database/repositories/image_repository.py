from __future__ import annotations

import os
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Optional

from src.domain.entities.image import ImageEntity

try:
    from supabase import Client
except Exception:  # pragma: no cover
    Client = object  # type: ignore

# module-level in-memory store for disabled mode
_MEM_IMAGES: dict[str, ImageEntity] = {}


class ImageRepository:
    def __init__(self, client: Optional[Client]) -> None:
        self.client = client
        self.disabled = os.getenv("SUPABASE_DISABLED", "0") == "1"
        # in-memory fallback
        self._mem: dict[str, ImageEntity] = {}

    def create(
        self,
        user_id: str,
        path: str,
        width: int,
        height: int,
        mime_type: str,
        original_id: Optional[str] = None,
        original_filename: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> ImageEntity:
        now = datetime.now(timezone.utc)
        if self.disabled or self.client is None:
            image_id = f"img_{len(_MEM_IMAGES)+1}"
            entity = ImageEntity(
                id=image_id,
                user_id=user_id,
                path=path,
                width=width,
                height=height,
                mime_type=mime_type,
                created_at=now,
                original_id=original_id,
                original_filename=original_filename,
                file_size=file_size,
            )
            _MEM_IMAGES[entity.id] = entity
            return entity
        # real insert
        try:  # pragma: no cover - network
            entity = ImageEntity(
                id="",
                user_id=user_id,
                path=path,
                width=width,
                height=height,
                mime_type=mime_type,
                created_at=now,
                original_id=original_id,
                original_filename=original_filename,
                file_size=file_size,
            )
            data = asdict(entity)
            data.pop("id")
            data["created_at"] = now.isoformat()
            # map to DB columns: storage_path instead of path
            data["storage_path"] = data.pop("path")
            res = self.client.table("images").insert(data).execute()
            row = res.data[0]
            return ImageEntity(
                id=row["id"],
                user_id=row["user_id"],
                path=row["storage_path"],
                width=row["width"],
                height=row["height"],
                mime_type=row["mime_type"],
                created_at=datetime.fromisoformat(row["created_at"]),
                original_id=row.get("original_id"),
                original_filename=row["original_filename"],
                file_size=row["file_size"],
            )
        except Exception as exc:
            raise RuntimeError(f"DB insert image failed: {exc}")

    def list_by_user(self, user_id: str) -> list[ImageEntity]:
        if self.disabled or self.client is None:
            return [img for img in _MEM_IMAGES.values() if img.user_id == user_id]
        try:  # pragma: no cover - network
            res = self.client.table("images").select("*").eq("user_id", user_id).execute()
            rows = res.data or []
            out: list[ImageEntity] = []
            for row in rows:
                out.append(
                    ImageEntity(
                        id=row["id"],
                        user_id=row["user_id"],
                        path=row["storage_path"],
                        width=row["width"],
                        height=row["height"],
                        mime_type=row["mime_type"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        original_id=row.get("original_id"),
                        original_filename=row["original_filename"],
                        file_size=row["file_size"],
                    )
                )
            return out
        except Exception as exc:
            raise RuntimeError(f"DB list images failed: {exc}")

    def get(self, image_id: str) -> Optional[ImageEntity]:
        if self.disabled or self.client is None:
            return _MEM_IMAGES.get(image_id)
        try:  # pragma: no cover - network
            res = self.client.table("images").select("*").eq("id", image_id).single().execute()
            row = res.data
            if not row:
                return None
            return ImageEntity(
                id=row["id"],
                user_id=row["user_id"],
                path=row["storage_path"],
                width=row["width"],
                height=row["height"],
                mime_type=row["mime_type"],
                created_at=datetime.fromisoformat(row["created_at"]),
                original_id=row.get("original_id"),
                original_filename=row["original_filename"],
                file_size=row["file_size"],
            )
        except Exception:
            return None

    def get_public_url(self, storage_path: str) -> str:
        if self.disabled or self.client is None:
            return f"/local-storage/{storage_path}"
        try:  # pragma: no cover - network
            bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "images")
            res = self.client.storage.from_(bucket).get_public_url(storage_path)  # type: ignore[attr-defined]
            return res
        except Exception:
            return ""

    def delete(self, image_id: str) -> bool:
        if self.disabled or self.client is None:
            return _MEM_IMAGES.pop(image_id, None) is not None
        try:  # pragma: no cover - network
            self.client.table("images").delete().eq("id", image_id).execute()
            return True
        except Exception:
            return False
