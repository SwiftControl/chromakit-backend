from __future__ import annotations

from fastapi import FastAPI

from src.infrastructure.api.middlewares import add_default_middlewares
from src.infrastructure.api.routes.auth_routes import router as auth_router
from src.infrastructure.api.routes.history_routes import router as history_router
from src.infrastructure.api.routes.image_routes import router as image_router
from src.infrastructure.api.routes.processing_routes import router as processing_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="ChromaKit Backend",
        version="0.1.0",
        description="""
        ## ChromaKit Backend API

        FastAPI backend for academic image processing using NumPy (no OpenCV), Clean 
        Architecture, and Supabase for auth, database, and storage.

        ### Features
        - **Authentication**: Token-based authentication with Supabase
        - **Image Management**: Upload, list, download, and delete images
        - **Image Processing**: Various image processing operations including brightness, 
          contrast, filters, and transformations
        - **History Tracking**: Track all processing operations performed on images
        - **Clean Architecture**: Domain-driven design with clear separation of concerns

        ### Authentication
        All endpoints (except root and health) require authentication via Bearer token 
        in the Authorization header:
        ```
        Authorization: Bearer your-jwt-token
        ```

        ### Error Responses
        All endpoints may return the following error responses:
        - **400 Bad Request**: Invalid request parameters or malformed data
        - **401 Unauthorized**: Missing or invalid authentication token
        - **404 Not Found**: Requested resource does not exist or user doesn't have access
        - **422 Unprocessable Entity**: Validation error in request body
        - **500 Internal Server Error**: Unexpected server error
        """,
        contact={
            "name": "ChromaKit Team",
            "email": "support@chromakit.com",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
    )
    add_default_middlewares(app)

    @app.get(
        "/",
        summary="API Root",
        description="Get basic information about the ChromaKit API",
        response_description="API information including status and version",
    )
    def root():
        """Get API root information."""
        return {"status": "ok", "service": "chromakit-backend", "version": app.version}

    @app.get(
        "/health",
        summary="Health Check",
        description="Check if the API service is running and healthy",
        response_description="Health status of the API service",
    )
    def health():
        """Check API health status."""
        return {"status": "healthy"}

    app.include_router(auth_router)
    app.include_router(image_router)
    app.include_router(processing_router)
    app.include_router(history_router)
    return app


app = create_app()
