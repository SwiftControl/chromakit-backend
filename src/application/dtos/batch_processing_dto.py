from __future__ import annotations

from pydantic import BaseModel, Field


class ProcessingOperation(BaseModel):
    """Individual processing operation with its parameters."""

    operation: str = Field(
        ...,
        description="Type of operation to apply",
        example="brightness",
    )
    params: dict = Field(
        default_factory=dict,
        description="Operation-specific parameters",
        example={"factor": 1.2},
    )


class BatchProcessRequest(BaseModel):
    """Request model for batch image processing with multiple operations."""

    image_id: str = Field(
        ...,
        description="ID of the image to process (operations will be applied to the root/original)",
        example="img_123456",
    )
    operations: list[ProcessingOperation] = Field(
        ...,
        description="List of operations to apply in sequence to the original image",
        min_items=1,
        example=[
            {"operation": "brightness", "params": {"factor": 1.2}},
            {"operation": "log_contrast", "params": {"k": 1.5}},
            {"operation": "grayscale_luminosity", "params": {}},
        ],
    )


class BatchProcessResponse(BaseModel):
    """Response model for batch image processing."""

    id: str = Field(..., description="ID of the resulting processed image")
    url: str = Field(..., description="Public URL to access the processed image")
    width: int = Field(..., description="Width of the processed image in pixels")
    height: int = Field(..., description="Height of the processed image in pixels")
    mime_type: str = Field(..., description="MIME type of the processed image")
    operations_applied: list[ProcessingOperation] = Field(
        ..., description="List of operations that were successfully applied"
    )
    original_image_id: str = Field(..., description="ID of the original source image")
    root_image_id: str = Field(..., description="ID of the root/original image in the chain")
    created_at: str = Field(..., description="ISO timestamp of when the image was created")
