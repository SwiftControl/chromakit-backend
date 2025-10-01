from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    id: str
    user_id: str
    path: str
    width: int
    height: int
    mime_type: str
    created_at: datetime
    original_id: Optional[str] = None
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    url: Optional[str] = None


class UploadImageResponse(BaseModel):
    image: ImageMetadata


class ListImagesResponse(BaseModel):
    images: list[ImageMetadata]
    total: int
    limit: int
    offset: int


class DeleteImageResponse(BaseModel):
    ok: bool = Field(default=True)


class ProcessImageRequest(BaseModel):
    image_id: str
    params: dict = Field(default_factory=dict)


class ProcessImageResponse(BaseModel):
    image: ImageMetadata
    operation: str
    params: dict


# Specific processing request DTOs
class BrightnessRequest(BaseModel):
    image_id: str
    factor: float


class ContrastRequest(BaseModel):
    image_id: str
    type: str  # "logarithmic" | "exponential"
    intensity: float


class ChannelRequest(BaseModel):
    image_id: str
    channel: str  # red|green|blue|cyan|magenta|yellow
    enabled: bool


class GrayscaleRequest(BaseModel):
    image_id: str
    method: str  # average|luminosity|midgray


class NegativeRequest(BaseModel):
    image_id: str


class BinarizeRequest(BaseModel):
    image_id: str
    threshold: float


class TranslateRequest(BaseModel):
    image_id: str
    dx: int
    dy: int


class RotateRequest(BaseModel):
    image_id: str
    angle: float


class CropRequest(BaseModel):
    image_id: str
    x_start: int
    x_end: int
    y_start: int
    y_end: int


class ReduceResolutionRequest(BaseModel):
    image_id: str
    factor: int


class EnlargeRegionRequest(BaseModel):
    image_id: str
    x_start: int
    x_end: int
    y_start: int
    y_end: int
    zoom_factor: int


class MergeImagesRequest(BaseModel):
    image1_id: str
    image2_id: str
    transparency: float
