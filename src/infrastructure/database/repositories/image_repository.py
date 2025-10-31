from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, datetime

from src.domain.entities.image import ImageEntity
from src.infrastructure.database.postgres_client import get_postgres_client

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
        self.use_local_db = os.getenv("USE_LOCAL_DB", "0") == "1"
        self.pg_client = get_postgres_client() if self.use_local_db else None
        # in-memory fallback
        self._mem: dict[str, ImageEntity] = {}

    def _row_to_entity(self, row: dict) -> ImageEntity:
        """Convert database row to ImageEntity."""
        # Handle timestamp field - PostgreSQL returns datetime object, Supabase returns ISO string
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        return ImageEntity(
            id=row["id"],
            user_id=row["user_id"],
            path=row.get("storage_path", row.get("path", "")),
            width=row["width"],
            height=row["height"],
            mime_type=row["mime_type"],
            created_at=created_at,
            original_id=row.get("original_id"),
            original_filename=row.get("original_filename"),
            file_size=row.get("file_size"),
            root_image_id=row.get("root_image_id"),
            parent_version_id=row.get("parent_version_id"),
            version_number=row.get("version_number", 1),
            is_root=row.get("is_root", True),
            base_image_id=row.get("base_image_id"),
        )

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
        
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            try:
                query = """
                    INSERT INTO images (
                        user_id, storage_path, width, height, mime_type,
                        original_filename, file_size, original_id,
                        root_image_id, parent_version_id, version_number,
                        is_root, base_image_id, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """
                row = self.pg_client.execute_insert(
                    query,
                    (
                        user_id, path, width, height, mime_type,
                        original_filename, file_size, original_id,
                        root_image_id, parent_version_id, version_number,
                        is_root, base_image_id, now
                    ),
                )
                return ImageEntity(
                    id=row["id"],
                    user_id=row["user_id"],
                    path=row["storage_path"],
                    width=row["width"],
                    height=row["height"],
                    mime_type=row["mime_type"],
                    created_at=row["created_at"],
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
                raise RuntimeError(f"PostgreSQL insert image failed: {exc}") from exc
        
        # In-memory mode
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
        
        # Supabase mode
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
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            query = "SELECT * FROM images WHERE user_id = %s ORDER BY created_at DESC"
            rows = self.pg_client.execute_many(query, (user_id,))
            return [self._row_to_entity(row) for row in rows]
        
        # In-memory mode
        if self.disabled or self.client is None:
            return [img for img in _MEM_IMAGES.values() if img.user_id == user_id]
        
        # Supabase mode
        try:  # pragma: no cover - network
            res = self.client.table("images").select("*").eq("user_id", user_id).execute()
            rows = res.data or []
            return [self._row_to_entity(row) for row in rows]
        except Exception as exc:
            raise RuntimeError(f"DB list images failed: {exc}") from exc

    def get(self, image_id: str) -> ImageEntity | None:
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            query = "SELECT * FROM images WHERE id = %s"
            row = self.pg_client.execute_one(query, (image_id,))
            return self._row_to_entity(row) if row else None
        
        # In-memory mode
        if self.disabled or self.client is None:
            return _MEM_IMAGES.get(image_id)
        
        # Supabase mode
        try:  # pragma: no cover - network
            res = self.client.table("images").select("*").eq("id", image_id).single().execute()
            row = res.data
            return self._row_to_entity(row) if row else None
        except Exception:
            return None

    def get_public_url(self, storage_path: str) -> str:
        # Local mode (both PostgreSQL and in-memory use local storage)
        if self.use_local_db or self.disabled or self.client is None:
            return f"/local-storage/{storage_path}"
        
        # Supabase mode
        try:  # pragma: no cover - network
            bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "images")
            res = self.client.storage.from_(bucket).get_public_url(storage_path)  # type: ignore[attr-defined]
            return res
        except Exception:
            return ""

    def delete(self, image_id: str) -> bool:
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            query = "DELETE FROM images WHERE id = %s"
            affected = self.pg_client.execute_update(query, (image_id,))
            return affected > 0
        
        # In-memory mode
        if self.disabled or self.client is None:
            return _MEM_IMAGES.pop(image_id, None) is not None
        
        # Supabase mode
        try:  # pragma: no cover - network
            self.client.table("images").delete().eq("id", image_id).execute()
            return True
        except Exception:
            return False

    def get_version_chain(self, root_image_id: str, user_id: str) -> list[ImageEntity]:
        """Get all versions in a chain, ordered by version number."""
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            # Get both root and derived versions in one query
            query = """
                SELECT * FROM images 
                WHERE user_id = %s AND (id = %s OR root_image_id = %s)
                ORDER BY version_number
            """
            rows = self.pg_client.execute_many(query, (user_id, root_image_id, root_image_id))
            return [self._row_to_entity(row) for row in rows]
        
        # In-memory mode
        if self.disabled or self.client is None:
            # Get all images for this root, including the root itself
            chain = [
                img
                for img in _MEM_IMAGES.values()
                if img.user_id == user_id
                and (img.root_image_id == root_image_id or img.id == root_image_id)
            ]
            return sorted(chain, key=lambda x: x.version_number)
        
        # Supabase mode
        try:  # pragma: no cover - network
            # Get the root image itself
            root_res = (
                self.client.table("images").select("*").eq("id", root_image_id).single().execute()
            )
            root_row = root_res.data
            results = []
            if root_row:
                results.append(self._row_to_entity(root_row))
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
                results.append(self._row_to_entity(row))
            return results
        except Exception as exc:
            raise RuntimeError(f"DB get version chain failed: {exc}") from exc

    def get_latest_version(self, root_image_id: str, user_id: str) -> ImageEntity | None:
        """Get the latest version in a chain."""
        # PostgreSQL mode
        if self.use_local_db and self.pg_client:
            query = """
                SELECT * FROM images 
                WHERE user_id = %s AND (id = %s OR root_image_id = %s)
                ORDER BY version_number DESC
                LIMIT 1
            """
            row = self.pg_client.execute_one(query, (user_id, root_image_id, root_image_id))
            return self._row_to_entity(row) if row else None
        
        # In-memory mode
        if self.disabled or self.client is None:
            chain = self.get_version_chain(root_image_id, user_id)
            return chain[-1] if chain else None
        
        # Supabase mode
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
            return self._row_to_entity(row)
        except Exception:
            return None
