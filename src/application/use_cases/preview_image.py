from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from src.domain.services.processing_service import ProcessingService
from src.infrastructure.database.repositories.image_repository import ImageRepository
from src.infrastructure.storage.supabase_storage import SupabaseStorage


@dataclass
class PreviewImageUseCase:
    """
    Preview image edits without saving to database.

    This use case applies operations to an image and returns the result
    WITHOUT creating a new version in the database. Perfect for:
    - Real-time preview while user adjusts parameters
    - "Try before you save" workflow
    - Temporary edits that user might discard

    The preview is always calculated from the ROOT/ORIGINAL image,
    not from the current preview state. This ensures:
    - Predictable results
    - No cumulative degradation
    - Each parameter change shows isolated effect

    Workflow:
    1. User uploads image (v1)
    2. User adjusts brightness slider → PreviewImageUseCase shows result (temp)
    3. User adjusts contrast slider → PreviewImageUseCase recalculates from v1 (temp)
    4. User clicks "Save" → ProcessImageUseCase creates v2 (permanent)
    """

    storage: SupabaseStorage
    image_repo: ImageRepository
    processing: ProcessingService

    def execute(
        self, user_id: str, image_id: str, operation: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Preview an image operation without saving.

        Args:
            user_id: The user making the request
            image_id: The image to use as base (will use its root)
            operation: The operation to apply
            params: Operation parameters

        Returns:
            Dictionary with:
            - preview_url: Temporary URL to preview image
            - width: Preview image width
            - height: Preview image height
            - operation: Operation applied
            - params: Parameters used
            - base_image_id: The root image used as base

        Note: The preview is NOT saved to database.
        """
        # Load the image reference
        image = self.image_repo.get(image_id)
        if image is None or image.user_id != user_id:
            raise ValueError("Image not found")

        # CRITICAL: Always use ROOT image as base for preview
        # This prevents cumulative effects when user adjusts parameters
        root_id = image.root_image_id if image.root_image_id else image.id
        root_image = self.image_repo.get(root_id)
        if root_image is None:
            raise ValueError("Root image not found")

        # Load the original image data
        src = self.storage.download_to_numpy(root_image.path)

        # Apply the operation
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
            out = self.processing.binarize(
                self.processing.grayscale_luminosity(src), float(params.get("threshold", 0.5))
            )
        elif op == "translate":
            out = self.processing.translate(src, int(params.get("dx", 0)), int(params.get("dy", 0)))
        elif op == "rotate":
            out = self.processing.rotate(src, float(params.get("angle", 0.0)))
        elif op == "crop":
            out = self.processing.crop(
                src,
                int(params["x_start"]),
                int(params["x_end"]),
                int(params["y_start"]),
                int(params["y_end"]),
            )
        elif op == "reduce_resolution":
            out = self.processing.reduce_resolution(src, int(params.get("factor", 2)))
        elif op == "enlarge_region":
            out = self.processing.enlarge_region(
                src,
                int(params["x_start"]),
                int(params["x_end"]),
                int(params["y_start"]),
                int(params["y_end"]),
                int(params.get("factor", 2)),
            )
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
            # For histogram, return the histogram data directly
            hist = self.processing.calculate_histogram(src)
            return {
                "type": "histogram",
                "histogram": hist,
                "base_image_id": root_id,
                "operation": op,
                "params": params,
            }
        else:
            raise ValueError("Unsupported operation")

        # Upload preview image to temporary storage
        # Note: This could be optimized to use a separate "preview" bucket
        # or include TTL for automatic cleanup
        ext = str(params.get("ext", "png"))
        stored = self.storage.upload_numpy(user_id=user_id, array=out, ext=ext)

        # Return preview information WITHOUT saving to database
        return {
            "type": "preview",
            "preview_url": self.image_repo.get_public_url(stored.path),
            "preview_path": stored.path,
            "width": stored.width,
            "height": stored.height,
            "operation": op,
            "params": params,
            "base_image_id": root_id,
            "is_temporary": True,
        }
