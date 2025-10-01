from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EditHistoryEntity:
    id: str
    user_id: str
    image_id: str
    operation_type: str
    parameters: dict[str, Any]
    result_storage_path: str | None
    created_at: datetime
