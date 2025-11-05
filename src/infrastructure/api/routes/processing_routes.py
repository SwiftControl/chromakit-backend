from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.application.dtos.batch_processing_dto import (
    BatchProcessRequest,
    BatchProcessResponse,
)
from src.application.dtos.common_dto import HistogramResponse, ProcessingOperationResponse
from src.application.dtos.image_dto import (
    BinarizeRequest,
    BrightnessRequest,
    ChannelRequest,
    ContrastRequest,
    CropRequest,
    EnlargeRegionRequest,
    GrayscaleRequest,
    ImageMetadata,
    MergeImagesRequest,
    NegativeRequest,
    ProcessImageRequest,
    ProcessImageResponse,
    ReduceResolutionRequest,
    ResetImageRequest,
    RotateRequest,
    TranslateRequest,
)
from src.application.use_cases.batch_process_image import BatchProcessImageUseCase
from src.application.use_cases.process_image import ProcessImageUseCase
from src.domain.services.processing_service import ProcessingService
from src.infrastructure.api.dependencies import (
    get_current_user,
    get_history_repo,
    get_image_repo,
    get_processing_service,
    get_storage,
)

router = APIRouter(
    prefix="/processing",
    tags=["Image Processing"],
    responses={
        400: {"description": "Bad Request - Invalid operation or parameters"},
        401: {"description": "Unauthorized - Invalid or missing authentication token"},
        404: {"description": "Not Found - Image does not exist or user doesn't have access"},
        422: {"description": "Validation Error - Invalid request format"},
    },
)


@router.post(
    "/batch",
    response_model=BatchProcessResponse,
    summary="Batch Process Image (Unified Endpoint)",
    description="""
    Apply multiple image processing operations in a single request.
    
    **Key Features:**
    - All operations are applied to the **root/original** image, not chained modifications
    - Multiple operations applied in sequence (brightness, contrast, channels, etc.)
    - Prevents cumulative degradation from modification over modification
    - Returns a single processed result with all modifications applied
    
    **How It Works:**
    1. System finds the root/original image (even if you reference a processed version)
    2. Applies all operations in order to that original
    3. Saves only the final result as a new version
    
    **Example Use Cases:**
    - Adjust brightness AND contrast in one request
    - Convert to grayscale AND adjust brightness
    - Modify multiple color channels at once
    - Apply any combination of filters and adjustments
    
    **Supported Operations:**
    - `brightness` - params: `{"factor": 1.2}`
    - `log_contrast` - params: `{"k": 1.5}`
    - `exp_contrast` - params: `{"k": 1.5}`
    - `invert` - params: `{}`
    - `grayscale_average` - params: `{}`
    - `grayscale_luminosity` - params: `{}`
    - `grayscale_midgray` - params: `{}`
    - `binarize` - params: `{"threshold": 0.5}`
    - `translate` - params: `{"dx": 10, "dy": 20}`
    - `rotate` - params: `{"angle": 45.0}`
    - `crop` - params: `{"x_start": 0, "x_end": 100, "y_start": 0, "y_end": 100}`
    - `reduce_resolution` - params: `{"factor": 2}`
    - `enlarge_region` - params: `{"x_start": 0, "x_end": 50, "y_start": 0, "y_end": 50, "factor": 2}`
    - `merge_images` - params: `{"other_image_id": "img_xyz", "transparency": 0.5}`
    - `channel_red` - params: `{"enabled": true}`
    - `channel_green` - params: `{"enabled": true}`
    - `channel_blue` - params: `{"enabled": false}`
    - `channel_cyan` - params: `{"enabled": true}`
    - `channel_magenta` - params: `{"enabled": true}`
    - `channel_yellow` - params: `{"enabled": true}`
    
    **Example Request:**
    ```json
    {
      "image_id": "img_123456",
      "operations": [
        {"operation": "brightness", "params": {"factor": 1.2}},
        {"operation": "log_contrast", "params": {"k": 1.5}},
        {"operation": "channel_blue", "params": {"enabled": false}}
      ]
    }
    ```
    
    **Response**: URL and metadata for the final processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the final processed image with all operations applied",
    responses={
        200: {"description": "Successfully processed image with all operations"},
        400: {"description": "Invalid operation or parameters"},
        404: {"description": "Image not found or access denied"},
    },
)
async def batch_process_image(
    body: BatchProcessRequest,
    user=Depends(get_current_user),
    storage=Depends(get_storage),
    image_repo=Depends(get_image_repo),
    history_repo=Depends(get_history_repo),
    processing: ProcessingService = Depends(get_processing_service),
):
    """
    Apply multiple operations to the root/original image in a single request.
    
    This is the RECOMMENDED endpoint for image processing as it:
    - Prevents cumulative modifications
    - Allows multiple adjustments in one operation
    - Always produces predictable results based on the original image
    """
    uc = BatchProcessImageUseCase(
        storage=storage,
        image_repo=image_repo,
        history_repo=history_repo,
        processing=processing,
    )

    try:
        # Convert operations to dict format
        operations_list = [
            {"operation": op.operation, "params": op.params} for op in body.operations
        ]
        
        entity = uc.execute(user.id, body.image_id, operations_list)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}") from e

    # Generate URL to access the processed image
    image_url = image_repo.get_public_url(entity.path)

    # Determine root image ID
    root_id = entity.root_image_id if entity.root_image_id else entity.id

    return BatchProcessResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operations_applied=body.operations,
        original_image_id=body.image_id,
        root_image_id=root_id,
        created_at=entity.created_at.isoformat(),
    )


@router.get(
    "/{image_id}/histogram",
    response_model=HistogramResponse,
    summary="Calculate Image Histogram",
    description="""
    Calculate and return the color histogram for an image.
    
    **For Grayscale Images:**
    Returns a single 'gray' channel with frequency distribution
    
    **For Color Images:**
    Returns separate 'red', 'green', and 'blue' channels with frequency distributions
    
    **Histogram Data:**
    - Each channel contains an array of frequency counts
    - Values represent pixel intensity distribution (0-255 range)
    - Useful for analyzing image brightness, contrast, and color balance
    
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only analyze their own images
    """,
    response_description="Histogram data with frequency distributions per color channel",
)
async def get_histogram(
    image_id: str,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Calculate and return color histogram for an image."""
    from src.infrastructure.api.dependencies import get_image_repo, get_storage
    from src.infrastructure.database.repositories.image_repository import ImageRepository
    from src.infrastructure.storage.supabase_storage import SupabaseStorage

    images: ImageRepository = get_image_repo()
    storage: SupabaseStorage = get_storage()
    entity = images.get(image_id)
    if entity is None or entity.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found")
    arr = storage.download_to_numpy(entity.path)
    hist = processing.calculate_histogram(arr)

    def to_dict(h):
        # map to spec-style keys
        if arr.ndim == 2:
            return {"gray": h["hist"].tolist()}
        else:
            return {
                "red": h["hist"][0].tolist(),
                "green": h["hist"][1].tolist(),
                "blue": h["hist"][2].tolist(),
            }

    return {"histogram": to_dict(hist)}


@router.post(
    "/brightness",
    response_model=ProcessingOperationResponse,
    summary="Adjust Image Brightness",
    description="""
    Adjust the brightness of an image and return URL to access the processed result.
    
    **Factor Guidelines:**
    - `1.0` = No change (original brightness)
    - `> 1.0` = Brighter (e.g., 1.5 = 50% brighter)
    - `< 1.0` = Darker (e.g., 0.7 = 30% darker)
    - `0.0` = Completely black
    
    **Technical Details:**
    - Linear brightness adjustment using NumPy
    - Preserves color ratios and image quality
    - Values are clamped to valid range [0, 1]
    - Creates new processed image accessible via returned URL
    - Saves operation to processing history
    
    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the processed image",
    responses={
        200: {"description": "Successfully processed image, returns URL and metadata"},
        400: {"description": "Invalid brightness factor (must be > 0)"},
        404: {"description": "Image not found or access denied"},
    },
)
async def op_brightness(
    body: BrightnessRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Adjust image brightness and return URL to the processed image."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "brightness", {"factor": body.factor})

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="brightness",
        parameters={"factor": body.factor},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/contrast",
    response_model=ProcessingOperationResponse,
    summary="Adjust Image Contrast",
    description="""
    Adjust the contrast of an image using logarithmic or exponential transformations 
    and return URL to the processed result.
    
    **Contrast Types:**
    - `logarithmic` - Compresses high values, expands low values (reduces harsh contrast)
    - `exponential` - Expands high values, compresses low values (increases dramatic contrast)
    
    **Intensity Guidelines:**
    - Higher values = more dramatic effect
    - `1.0` = Minimal adjustment
    - `> 1.0` = Stronger effect
    - Typical range: 0.5 - 3.0
    
    **Use Cases:**
    - Logarithmic: Enhance details in bright areas, reduce overexposure
    - Exponential: Enhance overall contrast, make images more dramatic
    
    **Technical Details:**
    - Uses NumPy mathematical transformations
    - Preserves image structure and quality
    - Creates new processed image accessible via returned URL
    
    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the processed image",
    responses={
        200: {"description": "Successfully processed image, returns URL and metadata"},
        400: {"description": "Invalid contrast type (must be 'logarithmic' or 'exponential')"},
        404: {"description": "Image not found or access denied"},
    },
)
async def op_contrast(
    body: ContrastRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Adjust image contrast and return URL to the processed image."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    if body.type not in ("logarithmic", "exponential"):
        raise HTTPException(
            status_code=400, detail="Contrast type must be 'logarithmic' or 'exponential'"
        )

    operation = "log_contrast" if body.type == "logarithmic" else "exp_contrast"
    entity = uc.execute(user.id, body.image_id, operation, {"k": body.intensity})

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation=f"contrast_{body.type}",
        parameters={"type": body.type, "intensity": body.intensity},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/negative",
    response_model=ProcessingOperationResponse,
    summary="Create Image Negative",
    description="""
    Create a negative (inverted) version of the image and return URL to access the processed result.
    
    **Effect:**
    - Inverts all pixel values (white becomes black, black becomes white)
    - Colors become their complementary colors
    - Useful for artistic effects, X-ray simulation, or image analysis
    
    **Technical Details:**
    - Formula: output = 1.0 - input (for normalized values)
    - Preserves image structure and details perfectly
    - Works on both grayscale and color images
    - Uses NumPy for efficient processing
    - Creates new processed image accessible via returned URL
    
    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the processed negative image",
    responses={
        200: {"description": "Successfully processed image, returns URL and metadata"},
        404: {"description": "Image not found or access denied"},
    },
)
async def op_negative(
    body: NegativeRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Create negative (inverted) version of the image."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "invert", {})

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="negative",
        parameters={},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/reset",
    response_model=ProcessingOperationResponse,
    summary="Reset Image to Original",
    description="""
    Reset an image to its original uploaded version, removing all applied filters and edits.
    
    **Use Cases:**
    - Remove all filters and start fresh
    - Return to original after multiple edits
    - Undo all processing operations at once
    
    **How It Works:**
    - Finds the root/original image in the version chain
    - Creates a new version pointing back to the original
    - Maintains edit history for tracking
    - Returns URL to the original image
    
    **Technical Details:**
    - Uses root_image_id to find original version
    - No image processing required - references existing file
    - Fast operation as it doesn't re-process the image
    - Creates new database entry for version tracking
    
    **Response**: URL and metadata of the original image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only reset their own images
    """,
    response_description="URL and metadata of the original (reset) image",
    responses={
        200: {"description": "Successfully reset to original, returns URL and metadata"},
        404: {"description": "Image not found or access denied"},
    },
)
async def op_reset(
    body: ResetImageRequest,
    user=Depends(get_current_user),
    image_repo=Depends(get_image_repo),
    history_repo=Depends(get_history_repo),
):
    """Reset image to its original (root) version."""
    # Get the current image
    image = image_repo.get(body.image_id)
    if image is None or image.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found")

    # Find the root image
    root_id = image.root_image_id if image.root_image_id else image.id
    root_image = image_repo.get(root_id)

    if root_image is None:
        raise HTTPException(status_code=404, detail="Original image not found")

    # If already at root, just return the current image
    if image.id == root_id:
        image_url = image_repo.get_public_url(root_image.path)
        return ProcessingOperationResponse(
            id=root_image.id,
            url=image_url,
            width=root_image.width,
            height=root_image.height,
            mime_type=root_image.mime_type,
            operation="reset",
            parameters={},
            original_image_id=body.image_id,
            created_at=root_image.created_at.isoformat(),
        )

    # Get current max version number for this root
    version_chain = image_repo.get_version_chain(root_id, user.id)
    next_version = max((v.version_number for v in version_chain), default=0) + 1

    # Create new version pointing to the root image
    entity = image_repo.create(
        user_id=user.id,
        path=root_image.path,  # Reuse root image path
        width=root_image.width,
        height=root_image.height,
        mime_type=root_image.mime_type,
        original_id=image.id,  # Parent is the current image
        original_filename=root_image.original_filename,
        file_size=root_image.file_size,
        root_image_id=root_id,
        parent_version_id=image.id,
        version_number=next_version,
        is_root=False,
        base_image_id=root_id,  # Base is the root image
    )

    # Record in history
    history_repo.create(
        user_id=user.id,
        image_id=entity.id,
        operation_type="reset",
        parameters={},
        result_storage_path=entity.path,
        source_image_id=image.id,
        root_image_id=root_id,
    )

    # Generate URL to access the original image
    image_url = image_repo.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="reset",
        parameters={},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/grayscale",
    response_model=ProcessingOperationResponse,
    summary="Convert Image to Grayscale",
    description="""
    Convert a color image to grayscale using different methods and return URL to 
    access the processed result.
    
    **Conversion Methods:**
    - `average` - Simple average of R, G, B channels: (R + G + B) / 3
    - `luminosity` - Weighted average based on human eye sensitivity: 0.299*R + 0.587*G + 0.114*B  
    - `midgray` - Uses the middle value: (max(R,G,B) + min(R,G,B)) / 2
    
    **Method Recommendations:**
    - `luminosity` - Most perceptually accurate (recommended for most uses)
    - `average` - Simple and fast computational approach
    - `midgray` - Preserves brightness relationships and contrast
    
    **Technical Details:**
    - Converts RGB color space to single-channel grayscale
    - Uses NumPy for efficient mathematical operations
    - Maintains image dimensions and quality
    - Creates new processed image accessible via returned URL
    
    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the processed grayscale image",
    responses={
        200: {"description": "Successfully processed image, returns URL and metadata"},
        400: {
            "description": "Invalid grayscale method (must be 'average', 'luminosity', "
            "or 'midgray')"
        },
        404: {"description": "Image not found or access denied"},
    },
)
async def op_grayscale(
    body: GrayscaleRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Convert color image to grayscale using specified method."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    mapping = {
        "average": "grayscale_average",
        "luminosity": "grayscale_luminosity",
        "midgray": "grayscale_midgray",
    }
    if body.method not in mapping:
        raise HTTPException(
            status_code=400, detail="Grayscale method must be 'average', 'luminosity', or 'midgray'"
        )

    entity = uc.execute(user.id, body.image_id, mapping[body.method], {})

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation=f"grayscale_{body.method}",
        parameters={"method": body.method},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/binarize",
    response_model=ProcessingOperationResponse,
    summary="Binarize Image",
    description="""
    Convert an image to binary (black and white) using a threshold value and return 
    URL to access the processed result.
    
    **Threshold Guidelines:**
    - `0.0` = Everything becomes white (lowest threshold)
    - `0.5` = Middle threshold (typical starting point)
    - `1.0` = Everything becomes black (highest threshold)
    - Pixels above threshold become white, below become black
    
    **Use Cases:**
    - Text recognition preprocessing
    - Shape detection and analysis
    - Creating high-contrast artistic effects
    - Document scanning enhancement
    
    **Technical Details:**
    - Converts image to grayscale first if needed
    - Applies threshold using NumPy comparison operations
    - Results in pure black and white image (no gray levels)
    - Creates new processed image accessible via returned URL
    
    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the binarized image",
    responses={
        200: {"description": "Successfully processed image, returns URL and metadata"},
        400: {"description": "Invalid threshold value (must be between 0.0 and 1.0)"},
        404: {"description": "Image not found or access denied"},
    },
)
async def op_binarize(
    body: BinarizeRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Convert image to binary (black and white) using threshold."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "binarize", {"threshold": body.threshold})

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="binarize",
        parameters={"threshold": body.threshold},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/translate",
    response_model=ProcessingOperationResponse,
    summary="Translate Image",
    description="""
    Translate (move) an image by specified horizontal and vertical offsets and return
    URL to access the processed result.

    **Offset Guidelines:**
    - `dx`: Horizontal offset in pixels (positive = right, negative = left)
    - `dy`: Vertical offset in pixels (positive = down, negative = up)

    **Use Cases:**
    - Repositioning images
    - Creating animation frames
    - Adjusting image alignment
    - Image composition

    **Technical Details:**
    - Uses NumPy array manipulation for efficient translation
    - Empty areas filled with appropriate background color
    - Preserves image dimensions
    - Creates new processed image accessible via returned URL

    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the translated image",
)
async def op_translate(
    body: TranslateRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Translate (move) image by specified horizontal and vertical offsets."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "translate", {"dx": body.dx, "dy": body.dy})

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="translate",
        parameters={"dx": body.dx, "dy": body.dy},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/rotate",
    response_model=ProcessingOperationResponse,
    summary="Rotate Image",
    description="""
    Rotate an image by a specified angle and return URL to access the processed result.
    
    **Angle Guidelines:**
    - Positive values = Counter-clockwise rotation
    - Negative values = Clockwise rotation  
    - Common angles: 90°, 180°, 270° for orthogonal rotations
    - Any decimal angle supported (e.g., 45.5°)
    
    **Technical Details:**
    - Uses NumPy geometric transformations
    - Preserves image quality with interpolation
    - May change image dimensions for non-90° rotations
    - Background filled with appropriate color
    - Creates new processed image accessible via returned URL
    
    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the rotated image",
)
async def op_rotate(
    body: RotateRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Rotate image by specified angle."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "rotate", {"angle": body.angle})

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="rotate",
        parameters={"angle": body.angle},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/crop",
    response_model=ProcessingOperationResponse,
    summary="Crop Image",
    description="""
    Crop an image to a specified rectangular region and return URL to access the processed result.
    
    **Coordinate System:**
    - Origin (0,0) is at top-left corner
    - X increases rightward, Y increases downward
    - All coordinates must be within image bounds
    - End coordinates must be greater than start coordinates
    
    **Parameters:**
    - `x_start`: Left edge of crop region
    - `x_end`: Right edge of crop region  
    - `y_start`: Top edge of crop region
    - `y_end`: Bottom edge of crop region
    
    **Technical Details:**
    - Uses NumPy array slicing for efficient cropping
    - Preserves image quality and color depth
    - Reduces file size proportionally to cropped area
    - Creates new processed image accessible via returned URL
    
    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the cropped image",
)
async def op_crop(
    body: CropRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Crop image to specified rectangular region."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    params = {
        "x_start": body.x_start,
        "x_end": body.x_end,
        "y_start": body.y_start,
        "y_end": body.y_end,
    }
    entity = uc.execute(user.id, body.image_id, "crop", params)

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="crop",
        parameters=params,
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/reduce-resolution",
    response_model=ProcessingOperationResponse,
    summary="Reduce Image Resolution",
    description="""
    Reduce the resolution of an image by a specified factor and return URL to access
    the processed result.

    **Factor Guidelines:**
    - `2` = Half size (width/2, height/2)
    - `3` = One-third size (width/3, height/3)
    - `4` = Quarter size (width/4, height/4)
    - Valid range: 2-10

    **Use Cases:**
    - Creating thumbnail images
    - Reducing file size for faster loading
    - Optimizing images for web display
    - Creating image pyramids for multi-resolution viewing

    **Technical Details:**
    - Uses NumPy downsampling for efficient resolution reduction
    - Maintains aspect ratio
    - Preserves image quality with appropriate resampling
    - Creates new processed image accessible via returned URL

    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the reduced resolution image",
)
async def op_reduce_resolution(
    body: ReduceResolutionRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Reduce image resolution by specified factor."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "reduce_resolution", {"factor": body.factor})

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="reduce_resolution",
        parameters={"factor": body.factor},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/enlarge-region",
    response_model=ProcessingOperationResponse,
    summary="Enlarge Specific Region",
    description="""
    Enlarge (zoom) a specific rectangular region of an image and return URL to access
    the processed result.

    **Coordinate System:**
    - Origin (0,0) is at top-left corner
    - X increases rightward, Y increases downward
    - All coordinates must be within image bounds

    **Parameters:**
    - `x_start`, `x_end`: Left and right edges of region
    - `y_start`, `y_end`: Top and bottom edges of region
    - `zoom_factor`: Enlargement multiplier (1-10)

    **Use Cases:**
    - Magnifying details in images
    - Creating zoomed thumbnails
    - Detail inspection and analysis
    - Medical/scientific image examination

    **Technical Details:**
    - Extracts specified region and enlarges it
    - Uses interpolation for quality preservation
    - Result image size = region_size * zoom_factor
    - Creates new processed image accessible via returned URL

    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the enlarged region image",
)
async def op_enlarge_region(
    body: EnlargeRegionRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Enlarge a specific rectangular region of an image."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    params = {
        "x_start": body.x_start,
        "x_end": body.x_end,
        "y_start": body.y_start,
        "y_end": body.y_end,
        "factor": body.zoom_factor,
    }
    entity = uc.execute(user.id, body.image_id, "enlarge_region", params)

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="enlarge_region",
        parameters=params,
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/merge",
    response_model=ProcessingOperationResponse,
    summary="Merge Two Images",
    description="""
    Merge (blend) two images together with adjustable transparency and return URL to
    access the processed result.

    **Transparency Guidelines:**
    - `0.0` = Second image fully transparent (only first image visible)
    - `0.5` = Equal blend of both images (50/50 mix)
    - `1.0` = Second image fully opaque (second image dominates)

    **Requirements:**
    - Both images must belong to the authenticated user
    - Images are automatically resized if dimensions don't match
    - Result dimensions match the first (base) image

    **Use Cases:**
    - Creating watermarks or overlays
    - Blending multiple exposures
    - Artistic compositing
    - Creating double exposure effects

    **Technical Details:**
    - Uses alpha blending formula: result = img1 * (1 - alpha) + img2 * alpha
    - NumPy-based efficient pixel blending
    - Automatic dimension matching
    - Creates new processed image accessible via returned URL

    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only merge their own images
    """,
    response_description="URL and metadata of the merged image",
)
async def op_merge(
    body: MergeImagesRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Merge two images with adjustable transparency."""
    from src.application.use_cases.process_image import ProcessImageUseCase

    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(
        user.id,
        body.image1_id,
        "merge_images",
        {"other_image_id": body.image2_id, "transparency": body.transparency},
    )

    # Generate URL to access the processed image
    images = get_image_repo()
    image_url = images.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="merge_images",
        parameters={"image2_id": body.image2_id, "transparency": body.transparency},
        original_image_id=body.image1_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/channel",
    response_model=ProcessingOperationResponse,
    summary="Manipulate Color Channels",
    description="""
    Enable/disable specific color channels or extract CMY channels and return URL to 
    access the processed result.
    
    **⚠️ IMPORTANT:** For toggling multiple channels or re-enabling channels, use the 
    `/processing/batch` endpoint instead. See documentation for details.
    
    **Supported Channels:**
    - `red`, `green`, `blue` - RGB color channels
    - `cyan`, `magenta`, `yellow` - CMY color channels (computed)
    
    **Channel Operations:**
    - **RGB Channels (enabled=true)**: Shows ONLY this channel (isolates it, zeros out others)
    - **RGB Channels (enabled=false)**: Hides this channel (zeros it out, keeps others visible)
    - **CMY Channels**: Extract as grayscale representation
    
    **Common Pitfall:**
    ```
    # ❌ This will NOT work as expected:
    1. Disable green → Result: [R, 0, B]  ✓
    2. Enable green → Result: [0, G, 0]   ✗ Shows ONLY green!
    
    # ✅ Use batch endpoint instead:
    POST /processing/batch with all channel states
    ```
    
    **Use Cases:**
    - Isolating a single channel for analysis (enabled=true)
    - Removing a single channel effect (enabled=false for one operation)
    - For multiple channel adjustments: **Use `/processing/batch`**
    
    **Recommended Approach:**
    Use `/processing/batch` with multiple channel operations to avoid cumulative effects.
    See `/docs/CHANNEL_OPERATIONS_GUIDE.md` for examples.
    
    **Technical Details:**
    - Operations always applied to root/original image
    - RGB operations manipulate existing color channels
    - CMY channels computed as (1 - RGB) then extracted
    - Uses NumPy for efficient channel operations
    - Creates new processed image accessible via returned URL
    
    **Response**: URL and metadata for the processed image
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only process their own images
    """,
    response_description="URL and metadata of the channel-processed image",
)
async def op_channel(
    body: ChannelRequest,
    user=Depends(get_current_user),
    storage=Depends(get_storage),
    image_repo=Depends(get_image_repo),
    history_repo=Depends(get_history_repo),
    processing: ProcessingService = Depends(get_processing_service),
):
    """Process channel operations using ProcessImageUseCase to ensure root image is used."""
    # Use ProcessImageUseCase to ensure consistent base image selection
    uc = ProcessImageUseCase(
        storage=storage,
        image_repo=image_repo,
        history_repo=history_repo,
        processing=processing,
    )

    try:
        # Convert channel operation to use case format
        operation = f"channel_{body.channel.lower()}"
        params = {"enabled": body.enabled}

        entity = uc.execute(user.id, body.image_id, operation, params)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}") from e

    # Generate URL to access the processed image
    image_url = image_repo.get_public_url(entity.path)

    return ProcessingOperationResponse(
        id=entity.id,
        url=image_url,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        operation="channel",
        parameters={"channel": body.channel, "enabled": body.enabled},
        original_image_id=body.image_id,
        created_at=entity.created_at.isoformat(),
    )


@router.post(
    "/{operation}",
    response_model=ProcessImageResponse,
    summary="Generic Image Processing Operation",
    description="""
    **⚠️ DEPRECATED**: Use specific operation endpoints instead (e.g., /processing/brightness)
    
    Perform a generic image processing operation by operation name.
    
    **Supported Operations:**
    - `brightness` - Adjust image brightness
    - `contrast` - Adjust image contrast  
    - `grayscale` - Convert to grayscale
    - `invert` - Create negative image
    - `binarize` - Convert to binary (black/white)
    - `rotate` - Rotate image
    - `crop` - Crop image to specified region
    - `translate` - Move image position
    - `histogram` - Calculate color histogram (special case)
    
    **Authentication required**: Yes (Bearer token)
    """,
    response_description="Metadata of the processed image and operation details",
    deprecated=True,
)
async def process_image(
    operation: str,
    body: ProcessImageRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    """
    Process an image using a generic operation name.

    DEPRECATED: Use specific operation endpoints for better type safety and documentation.
    """
    # special case: histogram returns raw histogram data, not a stored image
    if operation.lower() == "histogram":
        from src.infrastructure.api.dependencies import get_image_repo  # lazy import for DI
        from src.infrastructure.database.repositories.image_repository import ImageRepository

        images: ImageRepository = get_image_repo()
        entity = images.get(body.image_id)
        if entity is None or entity.user_id != user.id:
            raise HTTPException(status_code=404, detail="Image not found")
        from src.infrastructure.api.dependencies import get_storage
        from src.infrastructure.storage.supabase_storage import SupabaseStorage

        storage: SupabaseStorage = get_storage()
        arr = storage.download_to_numpy(entity.path)
        hist = processing.calculate_histogram(arr)
        # Convert numpy arrays to lists for JSON
        return {
            "operation": "histogram",
            "bins": hist["bins"].tolist(),
            "hist": hist["hist"].tolist(),
        }

    # default: run processing use-case which persists new image and history
    from src.infrastructure.api.dependencies import get_history_repo, get_image_repo, get_storage
    from src.infrastructure.database.repositories.history_repository import HistoryRepository
    from src.infrastructure.database.repositories.image_repository import ImageRepository
    from src.infrastructure.storage.supabase_storage import SupabaseStorage

    storage: SupabaseStorage = get_storage()
    images: ImageRepository = get_image_repo()
    history: HistoryRepository = get_history_repo()

    uc = ProcessImageUseCase(
        storage=storage, image_repo=images, history_repo=history, processing=processing
    )
    try:
        entity = uc.execute(
            user_id=user.id, image_id=body.image_id, operation=operation, params=dict(body.params)
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ProcessImageResponse(
        image=ImageMetadata(
            id=entity.id,
            user_id=entity.user_id,
            path=entity.path,
            width=entity.width,
            height=entity.height,
            mime_type=entity.mime_type,
            created_at=entity.created_at,
            original_id=entity.original_id,
            original_filename=entity.original_filename,
            file_size=entity.file_size,
        ),
        operation=operation,
        params=body.params,
    )
