"""
Olivenet Social Media Bot - Facebook Graph API Helper
Handles posting to Facebook Pages.
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


class FacebookError(Exception):
    """Facebook API error."""
    def __init__(self, message: str, error_code: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


async def post_text_to_facebook(
    message: str,
    page_id: Optional[str] = None,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Post a text message to Facebook Page.

    Args:
        message: The post text
        page_id: Facebook Page ID (uses settings if not provided)
        access_token: Page Access Token (uses settings if not provided)

    Returns:
        API response containing post ID
    """
    page_id = page_id or settings.facebook_page_id
    access_token = access_token or settings.facebook_access_token

    if not page_id or not access_token:
        raise FacebookError("Facebook credentials not configured")

    url = f"{GRAPH_API_BASE}/{page_id}/feed"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            data={
                "message": message,
                "access_token": access_token
            },
            timeout=30.0
        )

        data = response.json()

        if "error" in data:
            error = data["error"]
            raise FacebookError(
                error.get("message", "Unknown error"),
                error.get("code")
            )

        logger.info(f"Posted to Facebook: {data.get('id')}")
        return data


async def upload_photo_to_facebook(
    image_path: str,
    page_id: Optional[str] = None,
    access_token: Optional[str] = None,
    published: bool = False
) -> str:
    """
    Upload a photo to Facebook (unpublished by default).

    Args:
        image_path: Path to the image file
        page_id: Facebook Page ID
        access_token: Page Access Token
        published: Whether to publish immediately

    Returns:
        Photo ID for use in posts
    """
    page_id = page_id or settings.facebook_page_id
    access_token = access_token or settings.facebook_access_token

    if not page_id or not access_token:
        raise FacebookError("Facebook credentials not configured")

    image_file = Path(image_path)
    if not image_file.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    url = f"{GRAPH_API_BASE}/{page_id}/photos"

    async with httpx.AsyncClient() as client:
        with open(image_path, "rb") as f:
            response = await client.post(
                url,
                data={
                    "access_token": access_token,
                    "published": str(published).lower()
                },
                files={"source": (image_file.name, f, "image/png")},
                timeout=60.0
            )

        data = response.json()

        if "error" in data:
            error = data["error"]
            raise FacebookError(
                error.get("message", "Unknown error"),
                error.get("code")
            )

        photo_id = data.get("id")
        logger.info(f"Uploaded photo to Facebook: {photo_id}")
        return photo_id


async def post_with_photo_to_facebook(
    message: str,
    image_path: str,
    page_id: Optional[str] = None,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Post a message with a photo to Facebook Page.

    Args:
        message: The post text
        image_path: Path to the image file
        page_id: Facebook Page ID
        access_token: Page Access Token

    Returns:
        API response containing post ID
    """
    page_id = page_id or settings.facebook_page_id
    access_token = access_token or settings.facebook_access_token

    if not page_id or not access_token:
        raise FacebookError("Facebook credentials not configured")

    image_file = Path(image_path)
    if not image_file.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    url = f"{GRAPH_API_BASE}/{page_id}/photos"

    async with httpx.AsyncClient() as client:
        with open(image_path, "rb") as f:
            response = await client.post(
                url,
                data={
                    "message": message,
                    "access_token": access_token,
                    "published": "true"
                },
                files={"source": (image_file.name, f, "image/png")},
                timeout=60.0
            )

        data = response.json()

        if "error" in data:
            error = data["error"]
            raise FacebookError(
                error.get("message", "Unknown error"),
                error.get("code")
            )

        logger.info(f"Posted with photo to Facebook: {data.get('id')}")
        return data


async def verify_token(
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify the Facebook access token.

    Args:
        access_token: Token to verify

    Returns:
        Token debug info
    """
    access_token = access_token or settings.facebook_access_token

    if not access_token:
        raise FacebookError("No access token provided")

    url = f"{GRAPH_API_BASE}/debug_token"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params={
                "input_token": access_token,
                "access_token": access_token
            },
            timeout=30.0
        )

        data = response.json()

        if "error" in data:
            error = data["error"]
            raise FacebookError(
                error.get("message", "Unknown error"),
                error.get("code")
            )

        return data.get("data", {})


async def get_page_info(
    page_id: Optional[str] = None,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get Facebook Page information.

    Args:
        page_id: Facebook Page ID
        access_token: Page Access Token

    Returns:
        Page information
    """
    page_id = page_id or settings.facebook_page_id
    access_token = access_token or settings.facebook_access_token

    if not page_id or not access_token:
        raise FacebookError("Facebook credentials not configured")

    url = f"{GRAPH_API_BASE}/{page_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params={
                "fields": "id,name,fan_count,followers_count",
                "access_token": access_token
            },
            timeout=30.0
        )

        data = response.json()

        if "error" in data:
            error = data["error"]
            raise FacebookError(
                error.get("message", "Unknown error"),
                error.get("code")
            )

        return data
