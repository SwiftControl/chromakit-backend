from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.domain.entities.image import ImageEntity
from src.infrastructure.database.repositories.image_repository import ImageRepository
from src.infrastructure.storage.supabase_storage import SupabaseStorage


@dataclass
class UploadImageUseCase:
    storage: SupabaseStorage
    image_repo: ImageRepository

    def execute(
        self,
        user_id: str,
        array: np.ndarray,
        ext: str,
        *,
        original_id: str | None = None,
        original_filename: str | None = None,
        file_size: int | None = None,
        mime_type: str | None = None,
    ) -> ImageEntity:
        stored = self.storage.upload_numpy(user_id=user_id, array=array, ext=ext)
        entity = self.image_repo.create(
            user_id=user_id,
            path=stored.path,
            width=stored.width,
            height=stored.height,
            mime_type=mime_type or stored.content_type,
            original_id=original_id,
            original_filename=original_filename,
            file_size=file_size,
        )
        return entity
