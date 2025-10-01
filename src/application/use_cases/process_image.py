from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from src.domain.entities.image import ImageEntity
from src.domain.services.processing_service import ProcessingService
from src.infrastructure.database.repositories.history_repository import HistoryRepository
from src.infrastructure.database.repositories.image_repository import ImageRepository
from src.infrastructure.storage.supabase_storage import SupabaseStorage


@dataclass
class ProcessImageUseCase:
    storage: SupabaseStorage
    image_repo: ImageRepository
    history_repo: HistoryRepository
    processing: ProcessingService

    def execute(self, user_id: str, image_id: str, operation: str, params: dict[str, Any]) -> ImageEntity:
        # load source image
        image = self.image_repo.get(image_id)
        if image is None or image.user_id != user_id:
            raise ValueError("Image not found")
        src = self.storage.download_to_numpy(image.path)
        # route operation
        op = operation.lower()
        out: np.ndarray
        if op == "brightness":
            out = self.processing.adjust_brightness(src, float(params.get("factor", 0.0)))
        elif op == "log_contrast":
            out = self.processing.adjust_log_contrast(src, float(params.get("k", 1.0)))
        elif op == "exp_contrast":
            out = self.processing.adjust_exp_contrast(src, float(params.get("k", 1.0)))
        elif op == "invert":
            out = self.processing.invert_color(src)
        elif op == "grayscale_average":
            out = self.processing.grayscale_average(src)
        elif op == "grayscale_luminosity":
            out = self.processing.grayscale_luminosity(src)
        elif op == "grayscale_midgray":
            out = self.processing.grayscale_midgray(src)
        elif op == "binarize":
            out = self.processing.binarize(self.processing.grayscale_luminosity(src), float(params.get("threshold", 0.5)))
        elif op == "translate":
            out = self.processing.translate(src, int(params.get("dx", 0)), int(params.get("dy", 0)))
        elif op == "rotate":
            out = self.processing.rotate(src, float(params.get("angle", 0.0)))
        elif op == "crop":
            out = self.processing.crop(src, int(params["x_start"]), int(params["x_end"]), int(params["y_start"]), int(params["y_end"]))
        elif op == "reduce_resolution":
            out = self.processing.reduce_resolution(src, int(params.get("factor", 2)))
        elif op == "enlarge_region":
            out = self.processing.enlarge_region(src, int(params["x_start"]), int(params["x_end"]), int(params["y_start"]), int(params["y_end"]), int(params.get("factor", 2)))
        elif op == "merge_images":
            other_id = params.get("other_image_id")
            if not other_id:
                raise ValueError("Missing other_image_id")
            other = self.image_repo.get(str(other_id))
            if other is None or other.user_id != user_id:
                raise ValueError("Other image not found")
            img2 = self.storage.download_to_numpy(other.path)
            out = self.processing.merge_images(src, img2, float(params.get("transparency", 0.5)))
        elif op == "histogram":
            # histogram is not persisted as image; return raises to guide route to different response
            raise NotImplementedError("histogram")
        else:
            raise ValueError("Unsupported operation")
        # persist processed image
        ext = str(params.get("ext", "png"))
        stored = self.storage.upload_numpy(user_id=user_id, array=out, ext=ext)
        entity = self.image_repo.create(
            user_id=user_id,
            path=stored.path,
            width=stored.width,
            height=stored.height,
            mime_type=stored.content_type,
            original_id=image.id,
        )
        # history
        self.history_repo.create(user_id=user_id, image_id=entity.id, operation=op, params=params)
        return entity
