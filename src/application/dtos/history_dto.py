from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class HistoryItem(BaseModel):
    id: str
    user_id: str
    image_id: str
    operation: str
    params: dict[str, Any]
    created_at: datetime


class ListHistoryResponse(BaseModel):
    history: list[HistoryItem]

