from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HistoryItem(BaseModel):
    """Represents a single image processing operation in the history."""
    id: str = Field(..., description="Unique identifier of the history entry", example="hist_123456")
    user_id: str = Field(..., description="ID of the user who performed the operation")
    image_id: str = Field(..., description="ID of the processed image", example="img_123456")
    operation: str = Field(..., description="Name of the processing operation", example="brightness")
    params: dict[str, Any] = Field(..., description="Parameters used for the operation", example={"factor": 1.2})
    created_at: datetime = Field(..., description="ISO timestamp when the operation was performed")


class ListHistoryResponse(BaseModel):
    """Response model for listing processing history with pagination."""
    history: list[HistoryItem] = Field(..., description="List of history items")


class DeleteHistoryResponse(BaseModel):
    """Response model for history deletion."""
    ok: bool = Field(True, description="Indicates whether the deletion was successful")

