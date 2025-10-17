from __future__ import annotations

import os
from dataclasses import asdict
from datetime import UTC, datetime

from src.domain.entities.image import ImageEntity

try:
    from supabase import Client
except Exception:  # pragma: no cover
    Client = object  # type: ignore

# module-level in-memory store for disabled mode
_MEM_IMAGES: dict[str, ImageEntity] = {}


class ImageRepository:
    def __init__(self, client: Client | None) -> None:
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
        original_filename: str,
        original_id: str | None = None,
        file_size: int | None = None,
        root_image_id: str | None = None,
        parent_version_id: str | None = None,
        version_number: int = 1,
        is_root: bool = True,
        base_image_id: str | None = None,
    ) -> ImageEntity:
        now = datetime.now(UTC)
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
                root_image_id=root_image_id,
                parent_version_id=parent_version_id,
                version_number=version_number,
                is_root=is_root,
                base_image_id=base_image_id,
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
                root_image_id=root_image_id,
                parent_version_id=parent_version_id,
                version_number=version_number,
                is_root=is_root,
                base_image_id=base_image_id,
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
                root_image_id=row.get("root_image_id"),
                parent_version_id=row.get("parent_version_id"),
                version_number=row.get("version_number", 1),
                is_root=row.get("is_root", True),
                base_image_id=row.get("base_image_id"),
            )
        except Exception as exc:
            raise RuntimeError(f"DB insert image failed: {exc}") from exc

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
                        root_image_id=row.get("root_image_id"),
                        parent_version_id=row.get("parent_version_id"),
                        version_number=row.get("version_number", 1),
                        is_root=row.get("is_root", True),
                        base_image_id=row.get("base_image_id"),
                    )
                )
            return out
        except Exception as exc:
            raise RuntimeError(f"DB list images failed: {exc}") from exc

    def get(self, image_id: str) -> ImageEntity | None:
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
                root_image_id=row.get("root_image_id"),
                parent_version_id=row.get("parent_version_id"),
                version_number=row.get("version_number", 1),
                is_root=row.get("is_root", True),
                base_image_id=row.get("base_image_id"),
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

    def get_version_chain(self, root_image_id: str, user_id: str) -> list[ImageEntity]:
        """Get all versions in a chain, ordered by version number."""
        if self.disabled or self.client is None:
            # Get all images for this root, including the root itself
            chain = [
                img
                for img in _MEM_IMAGES.values()
                if img.user_id == user_id
                and (img.root_image_id == root_image_id or img.id == root_image_id)
            ]
            return sorted(chain, key=lambda x: x.version_number)
        try:  # pragma: no cover - network
            # Get the root image itself
            root_res = (
                self.client.table("images").select("*").eq("id", root_image_id).single().execute()
            )
            root_row = root_res.data
            results = []
            if root_row:
                results.append(
                    ImageEntity(
                        id=root_row["id"],
                        user_id=root_row["user_id"],
                        path=root_row["storage_path"],
                        width=root_row["width"],
                        height=root_row["height"],
                        mime_type=root_row["mime_type"],
                        created_at=datetime.fromisoformat(root_row["created_at"]),
                        original_id=root_row.get("original_id"),
                        original_filename=root_row["original_filename"],
                        file_size=root_row["file_size"],
                        root_image_id=root_row.get("root_image_id"),
                        parent_version_id=root_row.get("parent_version_id"),
                        version_number=root_row.get("version_number", 1),
                        is_root=root_row.get("is_root", True),
                        base_image_id=root_row.get("base_image_id"),
                    )
                )
            # Get all versions derived from this root
            res = (
                self.client.table("images")
                .select("*")
                .eq("root_image_id", root_image_id)
                .eq("user_id", user_id)
                .order("version_number")
                .execute()
            )
            rows = res.data or []
            for row in rows:
                results.append(
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
                        root_image_id=row.get("root_image_id"),
                        parent_version_id=row.get("parent_version_id"),
                        version_number=row.get("version_number", 1),
                        is_root=row.get("is_root", True),
                        base_image_id=row.get("base_image_id"),
                    )
                )
            return results
        except Exception as exc:
            raise RuntimeError(f"DB get version chain failed: {exc}") from exc

    def get_latest_version(self, root_image_id: str, user_id: str) -> ImageEntity | None:
        """Get the latest version in a chain."""
        if self.disabled or self.client is None:
            chain = self.get_version_chain(root_image_id, user_id)
            return chain[-1] if chain else None
        try:  # pragma: no cover - network
            res = (
                self.client.table("images")
                .select("*")
                .eq("root_image_id", root_image_id)
                .eq("user_id", user_id)
                .order("version_number", desc=True)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            if not rows:
                # Maybe root_image_id itself is the latest (no derived versions yet)
                return self.get(root_image_id)
            row = rows[0]
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
                root_image_id=row.get("root_image_id"),
                parent_version_id=row.get("parent_version_id"),
                version_number=row.get("version_number", 1),
                is_root=row.get("is_root", True),
                base_image_id=row.get("base_image_id"),
            )
        except Exception:
            return None
