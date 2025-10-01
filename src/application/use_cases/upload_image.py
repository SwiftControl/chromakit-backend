from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from src.infrastructure.storage.supabase_storage import SupabaseStorage
from src.infrastructure.database.repositories.image_repository import ImageRepository
from src.domain.entities.image import ImageEntity


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
        original_id: Optional[str] = None,
        original_filename: Optional[str] = None,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None,
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
