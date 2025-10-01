"""Common DTOs for API responses and error handling."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Optional


class ErrorResponse(BaseModel):
    """Standard error response model."""
    detail: str = Field(..., description="Error message describing what went wrong")


class SuccessResponse(BaseModel):
    """Standard success response model."""
    ok: bool = Field(True, description="Indicates the operation was successful")
    message: Optional[str] = Field(None, description="Optional success message")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Health status", example="healthy")


class RootResponse(BaseModel):
    """Root endpoint response model."""
    status: str = Field(..., description="API status", example="ok")
    service: str = Field(..., description="Service name", example="chromakit-backend")
    version: str = Field(..., description="API version", example="0.1.0")


class ValidationErrorDetail(BaseModel):
    """Validation error detail model."""
    loc: list[str | int] = Field(..., description="Location of the error in the request")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


class ValidationErrorResponse(BaseModel):
    """Validation error response model."""
    detail: list[ValidationErrorDetail] = Field(..., description="List of validation errors")


class HistogramResponse(BaseModel):
    """Histogram calculation response model."""
    histogram: dict[str, list[int]] = Field(
        ..., 
        description="Histogram data with channel names as keys and frequency arrays as values",
        example={
            "red": [0, 5, 10, 15, 20],
            "green": [0, 3, 8, 12, 18],
            "blue": [0, 2, 6, 14, 22]
        }
    )


class ProcessingOperationResponse(BaseModel):
    """Response for image processing operations that create new images."""
    id: str = Field(..., description="Unique identifier of the processed image", example="img_processed_123456")
    url: str = Field(..., description="Public URL to access the processed image", example="https://api.example.com/images/img_123456/download")
    width: Optional[int] = Field(None, description="Width of the processed image in pixels", example=800)
    height: Optional[int] = Field(None, description="Height of the processed image in pixels", example=600)
    mime_type: Optional[str] = Field(None, description="MIME type of the processed image", example="image/png")
    operation: str = Field(..., description="The processing operation that was applied", example="brightness")
    parameters: dict = Field(default_factory=dict, description="Parameters used for the processing operation")
    original_image_id: str = Field(..., description="ID of the original image that was processed", example="img_123456")
    created_at: Optional[str] = Field(None, description="ISO timestamp when the processed image was created")