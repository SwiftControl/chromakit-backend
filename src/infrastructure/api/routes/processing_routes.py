from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

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
    RotateRequest,
    TranslateRequest,
)
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
    
    **Supported Channels:**
    - `red`, `green`, `blue` - RGB color channels
    - `cyan`, `magenta`, `yellow` - CMY color channels (computed)
    
    **Channel Operations:**
    - **RGB Channels (enabled=true)**: Zero out other channels, keep selected
    - **RGB Channels (enabled=false)**: Zero out selected channel, keep others  
    - **CMY Channels**: Extract as grayscale representation
    
    **Use Cases:**
    - Color analysis and debugging
    - Creating artistic color effects
    - Medical/scientific image analysis
    - Color-blind accessibility testing
    
    **Technical Details:**
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
    processing: ProcessingService = Depends(get_processing_service),
):
    # Implement minimal channel toggle/extract
    images = get_image_repo()
    storage = get_storage()
    history = get_history_repo()
    src_meta = images.get(body.image_id)
    if src_meta is None or src_meta.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found")
    arr = storage.download_to_numpy(src_meta.path)
    import numpy as np

    ch = body.channel.lower()
    rgb = np.repeat(arr[..., None], 3, axis=2) if arr.ndim == 2 else arr.copy()
    if ch in ("red", "green", "blue"):
        idx = {"red": 0, "green": 1, "blue": 2}[ch]
        if body.enabled:
            # zero-out other channels
            for c in range(3):
                if c != idx:
                    rgb[..., c] = 0
        else:
            rgb[..., idx] = 0
    elif ch in ("cyan", "magenta", "yellow"):
        # produce grayscale of selected CMY channel
        idx = {"cyan": 0, "magenta": 1, "yellow": 2}[ch]
        cmy = 1.0 - rgb[..., :3]
        rgb = cmy[..., idx]
    else:
        raise HTTPException(status_code=400, detail="Invalid channel")
    stored = storage.upload_numpy(user.id, rgb, ext="png")
    entity = images.create(
        user_id=user.id,
        path=stored.path,
        width=stored.width,
        height=stored.height,
        mime_type=stored.content_type,
        original_id=src_meta.id,
        original_filename=src_meta.original_filename,
        file_size=stored.size,
    )
    history.create(
        user.id, entity.id, "channel", {"channel": body.channel, "enabled": body.enabled}
    )

    # Generate URL to access the processed image
    image_url = images.get_public_url(entity.path)

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
