from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    """Comprehensive metadata for an image in the system."""
    id: str = Field(..., description="Unique identifier of the image", example="img_123456")
    user_id: str = Field(..., description="ID of the user who owns this image")
    path: str = Field(..., description="Storage path of the image file", example="user123/img_123456.png")
    width: int = Field(..., description="Width of the image in pixels", example=1920, gt=0)
    height: int = Field(..., description="Height of the image in pixels", example=1080, gt=0)
    mime_type: str = Field(..., description="MIME type of the image", example="image/png")
    created_at: datetime = Field(..., description="ISO timestamp when the image was created or uploaded")
    original_id: str | None = Field(None, description="ID of the original image if this is a processed version")
    original_filename: str | None = Field(None, description="Original filename when uploaded", example="photo.jpg")
    file_size: int | None = Field(None, description="Size of the image file in bytes", example=2048576)
    url: str | None = Field(None, description="Public URL to access the image", example="https://storage.example.com/image.png")


class UploadImageResponse(BaseModel):
    """Response model for successful image upload."""
    image: ImageMetadata = Field(..., description="Metadata of the uploaded image")


class ListImagesResponse(BaseModel):
    """Response model for listing user images with pagination."""
    images: list[ImageMetadata] = Field(..., description="List of image metadata objects")
    total: int = Field(..., description="Total number of images available", example=150, ge=0)
    limit: int = Field(..., description="Maximum number of images returned in this response", example=20, ge=1, le=100)
    offset: int = Field(..., description="Number of images skipped from the beginning", example=0, ge=0)


class DeleteImageResponse(BaseModel):
    """Response model for image deletion."""
    ok: bool = Field(True, description="Indicates whether the deletion was successful")


class ProcessImageRequest(BaseModel):
    """Generic request model for image processing operations."""
    image_id: str = Field(..., description="ID of the image to process", example="img_123456")
    params: dict = Field(default_factory=dict, description="Operation-specific parameters")


class ProcessImageResponse(BaseModel):
    """Response model for image processing operations."""
    image: ImageMetadata = Field(..., description="Metadata of the processed image")
    operation: str = Field(..., description="Name of the processing operation applied", example="brightness")
    params: dict = Field(..., description="Parameters used for the processing operation")


# Specific processing request DTOs
class BrightnessRequest(BaseModel):
    """Request model for brightness adjustment."""
    image_id: str = Field(..., description="ID of the image to adjust brightness", example="img_123456")
    factor: float = Field(..., description="Brightness factor (1.0 = no change, >1.0 = brighter, <1.0 = darker)", example=1.2, gt=0)


class ContrastRequest(BaseModel):
    """Request model for contrast adjustment."""
    image_id: str = Field(..., description="ID of the image to adjust contrast", example="img_123456")
    type: str = Field(..., description="Type of contrast adjustment", example="logarithmic", pattern="^(logarithmic|exponential)$")
    intensity: float = Field(..., description="Contrast intensity factor", example=1.5, gt=0)


class ChannelRequest(BaseModel):
    """Request model for color channel manipulation."""
    image_id: str = Field(..., description="ID of the image to modify channels", example="img_123456")
    channel: str = Field(..., description="Color channel to manipulate", example="red", pattern="^(red|green|blue|cyan|magenta|yellow)$")
    enabled: bool = Field(..., description="Whether to enable (True) or disable (False) the channel")


class GrayscaleRequest(BaseModel):
    """Request model for grayscale conversion."""
    image_id: str = Field(..., description="ID of the image to convert to grayscale", example="img_123456")
    method: str = Field(..., description="Grayscale conversion method", example="luminosity", pattern="^(average|luminosity|midgray)$")


class NegativeRequest(BaseModel):
    """Request model for negative/invert operation."""
    image_id: str = Field(..., description="ID of the image to invert", example="img_123456")


class BinarizeRequest(BaseModel):
    """Request model for image binarization."""
    image_id: str = Field(..., description="ID of the image to binarize", example="img_123456")
    threshold: float = Field(..., description="Binarization threshold (0.0 to 1.0)", example=0.5, ge=0.0, le=1.0)


class TranslateRequest(BaseModel):
    """Request model for image translation."""
    image_id: str = Field(..., description="ID of the image to translate", example="img_123456")
    dx: int = Field(..., description="Horizontal offset in pixels", example=50)
    dy: int = Field(..., description="Vertical offset in pixels", example=30)


class RotateRequest(BaseModel):
    """Request model for image rotation."""
    image_id: str = Field(..., description="ID of the image to rotate", example="img_123456")
    angle: float = Field(..., description="Rotation angle in degrees (positive = counterclockwise)", example=45.0)


class CropRequest(BaseModel):
    """Request model for image cropping."""
    image_id: str = Field(..., description="ID of the image to crop", example="img_123456")
    x_start: int = Field(..., description="Starting X coordinate (left edge)", example=100, ge=0)
    x_end: int = Field(..., description="Ending X coordinate (right edge)", example=500, ge=0)
    y_start: int = Field(..., description="Starting Y coordinate (top edge)", example=50, ge=0)
    y_end: int = Field(..., description="Ending Y coordinate (bottom edge)", example=300, ge=0)


class ReduceResolutionRequest(BaseModel):
    """Request model for reducing image resolution."""
    image_id: str = Field(..., description="ID of the image to reduce resolution", example="img_123456")
    factor: int = Field(..., description="Reduction factor (2 = half size, 3 = one third size, etc.)", example=2, ge=2, le=10)


class EnlargeRegionRequest(BaseModel):
    """Request model for enlarging a specific region of an image."""
    image_id: str = Field(..., description="ID of the image to enlarge a region from", example="img_123456")
    x_start: int = Field(..., description="Starting X coordinate of the region", example=100, ge=0)
    x_end: int = Field(..., description="Ending X coordinate of the region", example=300, ge=0)
    y_start: int = Field(..., description="Starting Y coordinate of the region", example=50, ge=0)
    y_end: int = Field(..., description="Ending Y coordinate of the region", example=200, ge=0)
    zoom_factor: int = Field(..., description="Enlargement factor for the selected region", example=2, ge=1, le=10)


class MergeImagesRequest(BaseModel):
    """Request model for merging two images."""
    image1_id: str = Field(..., description="ID of the first image (base image)", example="img_123456")
    image2_id: str = Field(..., description="ID of the second image (overlay image)", example="img_789012")
    transparency: float = Field(..., description="Transparency level for the overlay (0.0 = fully transparent, 1.0 = fully opaque)", example=0.5, ge=0.0, le=1.0)
