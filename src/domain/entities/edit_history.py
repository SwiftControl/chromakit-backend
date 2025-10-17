from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EditHistoryEntity:
    id: str
    user_id: str
    image_id: str  # The resulting image ID after this operation
    operation_type: str
    parameters: dict[str, Any]
    result_storage_path: str | None
    created_at: datetime
    # Enhanced tracking
    source_image_id: str | None = None  # The image ID used as input for this operation
    root_image_id: str | None = None  # The root/original image this operation chain belongs to
