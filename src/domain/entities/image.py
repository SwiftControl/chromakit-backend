from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ImageEntity:
    id: str
    user_id: str
    path: str  # storage path {user_id}/{uuid}.{ext}
    width: int
    height: int
    mime_type: str
    created_at: datetime
    original_id: Optional[str] = None  # if derived from another image
    original_filename: Optional[str] = None
    file_size: Optional[int] = None  # bytes

    # Backwards-compat property
    @property
    def content_type(self) -> str:
        return self.mime_type
