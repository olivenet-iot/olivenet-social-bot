"""
Olivenet Social Media Bot - FastAPI Application
REST API for content generation and posting.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .config import settings
from .claude_helper import generate_post_text, generate_visual_html
from .renderer import render_html_to_png, save_html_and_render, cleanup
from .facebook_helper import (
    post_text_to_facebook,
    post_with_photo_to_facebook,
    get_page_info,
    FacebookError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Olivenet Social Media API",
    description="API for generating and posting social media content",
    version="1.0.0"
)


# Request/Response Models
class GeneratePostRequest(BaseModel):
    topic: str = Field(..., description="Topic for the post", min_length=3)


class GeneratePostResponse(BaseModel):
    success: bool
    post_text: str
    topic: str


class GenerateVisualRequest(BaseModel):
    post_text: str = Field(..., description="Post text to visualize")
    topic: str = Field(..., description="Topic for context")


class GenerateVisualResponse(BaseModel):
    success: bool
    html_content: str
    topic: str


class RenderImageRequest(BaseModel):
    html_content: str = Field(..., description="HTML content to render")
    filename: Optional[str] = Field(None, description="Optional filename")


class RenderImageResponse(BaseModel):
    success: bool
    image_path: str
    html_path: Optional[str] = None


class PostToFacebookRequest(BaseModel):
    message: str = Field(..., description="Post message")
    image_path: Optional[str] = Field(None, description="Optional image path")


class PostToFacebookResponse(BaseModel):
    success: bool
    post_id: str
    message: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


# Startup/Shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    settings.ensure_directories()
    logger.info("Olivenet Social API started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    await cleanup()
    logger.info("Olivenet Social API stopped")


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


@app.post("/generate-post", response_model=GeneratePostResponse)
async def generate_post(request: GeneratePostRequest):
    """
    Generate post text using Claude Code.

    Uses context files to generate appropriate content.
    """
    try:
        logger.info(f"Generating post for topic: {request.topic}")
        post_text = await generate_post_text(request.topic)

        return GeneratePostResponse(
            success=True,
            post_text=post_text,
            topic=request.topic
        )
    except Exception as e:
        logger.error(f"Failed to generate post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-visual", response_model=GenerateVisualResponse)
async def generate_visual(request: GenerateVisualRequest):
    """
    Generate HTML visual for a post using Claude Code.

    Creates a 1080x1080px visual in Olivenet style.
    """
    try:
        logger.info(f"Generating visual for topic: {request.topic}")
        html_content = await generate_visual_html(request.post_text, request.topic)

        return GenerateVisualResponse(
            success=True,
            html_content=html_content,
            topic=request.topic
        )
    except Exception as e:
        logger.error(f"Failed to generate visual: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/render-image", response_model=RenderImageResponse)
async def render_image(request: RenderImageRequest):
    """
    Render HTML content to PNG image.

    Uses Playwright for high-quality rendering.
    """
    try:
        logger.info("Rendering HTML to PNG")

        # Generate filename if not provided
        if request.filename:
            base_name = Path(request.filename).stem
        else:
            base_name = f"visual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        html_path, image_path = await save_html_and_render(
            request.html_content,
            base_name
        )

        return RenderImageResponse(
            success=True,
            image_path=image_path,
            html_path=html_path
        )
    except Exception as e:
        logger.error(f"Failed to render image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/post-to-facebook", response_model=PostToFacebookResponse)
async def post_to_facebook(request: PostToFacebookRequest):
    """
    Post content to Facebook Page.

    Optionally includes an image.
    """
    try:
        logger.info("Posting to Facebook")

        if request.image_path:
            # Post with image
            result = await post_with_photo_to_facebook(
                message=request.message,
                image_path=request.image_path
            )
        else:
            # Text-only post
            result = await post_text_to_facebook(message=request.message)

        return PostToFacebookResponse(
            success=True,
            post_id=result.get("id", ""),
            message="Posted successfully"
        )
    except FacebookError as e:
        logger.error(f"Facebook error: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    except FileNotFoundError as e:
        logger.error(f"Image not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to post to Facebook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/facebook-status")
async def facebook_status():
    """Check Facebook connection status."""
    try:
        page_info = await get_page_info()
        return {
            "connected": True,
            "page_name": page_info.get("name"),
            "page_id": page_info.get("id"),
            "followers": page_info.get("followers_count")
        }
    except FacebookError as e:
        return {
            "connected": False,
            "error": e.message
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
