"""
Nano Banana Pro - fal.ai Image Generation for Infographics
Model: fal-ai/nano-banana-pro
- Text rendering with high accuracy
- Infographic, diagram, arrow-box visuals
- Queue-based async generation via fal.ai
"""

import os
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("nano_banana")

FAL_API_KEY = settings.fal_api_key or os.getenv("FAL_API_KEY", "")
OUTPUT_DIR = str(settings.outputs_dir)

# fal.ai endpoint config
FAL_BASE_URL = "https://queue.fal.run"
FAL_MODEL_ENDPOINT = "fal-ai/nano-banana-pro"

# Map Gemini-style aspect ratios to fal.ai image_size values
ASPECT_RATIO_MAP = {
    "1:1": "square_hd",
    "16:9": "landscape_16_9",
    "9:16": "portrait_9_16",
    "4:3": "landscape_4_3",
    "3:4": "portrait_4_3",
}

# Infographic style guidelines for Turkish IoT/Tech content
INFOGRAPHIC_STYLE_PROMPT = """
Create a professional infographic visual in MODERN TECH style:

DESIGN REQUIREMENTS:
- Clean, minimal design with olive green (#4a7c4a) and sky blue (#38bdf8) accents
- Use arrows, boxes, icons to show relationships
- Large, readable Turkish text (if any text is needed)
- Professional data visualization style
- 1:1 aspect ratio optimized for Instagram

VISUAL ELEMENTS:
- Gradient backgrounds (dark to light olive)
- Subtle grid patterns or tech patterns
- Rounded corners on boxes and containers
- Clear visual hierarchy with icons
- Modern sans-serif typography

AVOID:
- Human faces or realistic people
- Brand logos other than abstract tech icons
- Cluttered layouts
- Small unreadable text
- Stock photo style imagery
- Hashtags, social media tags, or # symbols

OUTPUT: High quality infographic suitable for Instagram post
"""


def add_logo_overlay(
    image_path: str,
    position: str = "bottom_left",
    logo_scale: float = 0.12,
    padding: int = 25,
    opacity: float = 0.85
) -> str:
    """
    Görsele Olivenet logosu ekle

    Args:
        image_path: Görsel dosya yolu
        position: Logo pozisyonu (bottom_left, bottom_right, top_left, top_right)
        logo_scale: Logo boyutu (görsel genişliğinin oranı)
        padding: Kenar boşluğu (piksel)
        opacity: Logo opaklığı (0.0 - 1.0)

    Returns:
        Güncellenmiş görsel yolu
    """
    from PIL import Image

    logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logo-icon.png")

    if not os.path.exists(logo_path):
        logger.warning(f"Logo bulunamadı: {logo_path}")
        return image_path

    try:
        image = Image.open(image_path).convert("RGBA")
        logo = Image.open(logo_path).convert("RGBA")

        # Logo boyutlandırma
        logo_width = int(image.width * logo_scale)
        logo_height = int(logo.height * (logo_width / logo.width))
        logo = logo.resize((logo_width, logo_height), Image.LANCZOS)

        # Opacity ayarı
        if opacity < 1.0:
            alpha = logo.split()[3]
            alpha = alpha.point(lambda p: int(p * opacity))
            logo.putalpha(alpha)

        # Pozisyon hesapla
        if position == "bottom_left":
            x = padding
            y = image.height - logo_height - padding
        elif position == "bottom_right":
            x = image.width - logo_width - padding
            y = image.height - logo_height - padding
        elif position == "top_left":
            x = padding
            y = padding
        elif position == "top_right":
            x = image.width - logo_width - padding
            y = padding
        else:
            x = padding
            y = image.height - logo_height - padding

        # Logo yapıştır
        image.paste(logo, (x, y), logo)

        # Üzerine kaydet
        image.convert("RGB").save(image_path, "PNG")
        logger.info(f"Logo eklendi: {image_path}")

        return image_path

    except Exception as e:
        logger.error(f"Logo ekleme hatası: {e}")
        return image_path


async def _fal_submit_and_poll(prompt: str, image_size: str = "square_hd") -> Dict[str, Any]:
    """
    Submit image generation request to fal.ai queue API and poll for result.

    Timeout: 3 minutes (image generation is faster than video)
    """
    headers = {
        "Authorization": f"Key {FAL_API_KEY}",
        "Content-Type": "application/json"
    }

    request_body = {
        "prompt": prompt,
        "image_size": image_size,
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Submit request
        submit_url = f"{FAL_BASE_URL}/{FAL_MODEL_ENDPOINT}"
        logger.debug(f"  Submitting to: {submit_url}")

        response = await client.post(submit_url, json=request_body, headers=headers)
        response.raise_for_status()

        result = response.json()

        # If result is ready immediately (sync response)
        if "images" in result:
            return result

        # Queue response - need to poll for result
        request_id = result.get("request_id")
        if not request_id:
            raise Exception(f"No request_id in response: {result}")

        logger.info(f"  Request queued: {request_id}")

        # Get polling URLs from response
        status_url = result.get("status_url")
        result_url = result.get("response_url")

        if not status_url or not result_url:
            # Fallback: construct URLs manually
            status_url = f"{FAL_BASE_URL}/{FAL_MODEL_ENDPOINT}/requests/{request_id}/status"
            result_url = f"{FAL_BASE_URL}/{FAL_MODEL_ENDPOINT}/requests/{request_id}"

        # Poll for result (3 minutes max, 3 second intervals)
        max_attempts = 60
        for attempt in range(max_attempts):
            await asyncio.sleep(3)

            status_response = await client.get(status_url, headers=headers)
            status_response.raise_for_status()
            status = status_response.json()

            current_status = status.get("status", "unknown")
            logger.debug(f"  Status [{attempt + 1}/{max_attempts}]: {current_status}")

            if current_status == "COMPLETED":
                result_response = await client.get(result_url, headers=headers)
                result_response.raise_for_status()
                return result_response.json()

            elif current_status in ["FAILED", "CANCELLED"]:
                error_msg = status.get("error", "Unknown error")
                raise Exception(f"fal.ai generation failed: {error_msg}")

            # IN_QUEUE or IN_PROGRESS - continue polling

        raise Exception("fal.ai generation timed out (3 minutes)")


async def _download_fal_image(image_url: str, filename_prefix: str) -> str:
    """Download image from fal.ai CDN and save as PNG."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    image_path = f"{OUTPUT_DIR}/{filename_prefix}_{timestamp}.png"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(image_url)
        response.raise_for_status()

        with open(image_path, "wb") as f:
            f.write(response.content)

    logger.info(f"  Image saved: {image_path} ({os.path.getsize(image_path)/1024:.1f} KB)")
    return image_path


async def generate_infographic(
    topic: str,
    content_text: str = "",
    style: str = "modern",
    language: str = "tr",
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    use_search: bool = True
) -> Dict[str, Any]:
    """
    Generate a single infographic image using Nano Banana Pro

    Args:
        topic: Main topic for the infographic
        content_text: Additional content/text to include
        style: Visual style (modern, minimal, colorful)
        language: Language for text (tr, en)
        aspect_ratio: Image ratio (1:1, 16:9, 9:16)
        resolution: Image size (kept for backward compat, mapped to fal.ai image_size)
        use_search: Kept for backward compat (no-op with fal.ai)

    Returns:
        Dict with success, image_path, error, etc.
    """

    if not FAL_API_KEY:
        return {"success": False, "error": "FAL_API_KEY not configured"}

    start_time = datetime.now()

    # Build the prompt
    prompt = _build_infographic_prompt(topic, content_text, style, language)

    # Map aspect ratio to fal.ai image_size
    fal_image_size = ASPECT_RATIO_MAP.get(aspect_ratio, "square_hd")

    logger.info(f"Nano Banana infographic generation starting...")
    logger.info(f"  Topic: {topic[:50]}...")
    logger.info(f"  Style: {style}, Image size: {fal_image_size}")

    try:
        # Generate via fal.ai
        logger.info("  Sending request to fal.ai nano-banana-pro...")

        result = await _fal_submit_and_poll(prompt, fal_image_size)

        # Extract image URL from response
        images = result.get("images", [])
        if not images:
            return {"success": False, "error": "No images in fal.ai response"}

        image_url = images[0].get("url")
        if not image_url:
            return {"success": False, "error": "No image URL in fal.ai response"}

        # Download image
        image_path = await _download_fal_image(image_url, "nano_banana")

        # Logo overlay devre dışı - içerikle çakışıyor
        # add_logo_overlay(image_path)

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "image_path": image_path,
            "file_size": os.path.getsize(image_path),
            "duration": elapsed,
            "text_response": "",
            "model": "fal-ai/nano-banana-pro",
            "cost_estimate": 0.15
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Nano Banana error: {error_msg}")
        return {"success": False, "error": error_msg}


async def generate_carousel_infographics(
    topic: str,
    slides: List[Dict[str, str]],
    style: str = "modern",
    language: str = "tr"
) -> Dict[str, Any]:
    """
    Generate multiple infographic images for carousel

    Args:
        topic: Main carousel topic
        slides: List of slide data [{"title": "...", "content": "..."}]
        style: Visual style
        language: Language for text

    Returns:
        Dict with success, image_paths list, errors, etc.
    """

    if not FAL_API_KEY:
        return {"success": False, "error": "FAL_API_KEY not configured"}

    if not slides:
        return {"success": False, "error": "No slides provided"}

    start_time = datetime.now()
    image_paths = []
    errors = []
    total_cost = 0

    slide_count = len(slides)
    logger.info(f"Nano Banana carousel generation starting...")
    logger.info(f"  Topic: {topic[:50]}...")
    logger.info(f"  Slides: {slide_count}")

    for i, slide in enumerate(slides, 1):
        slide_title = slide.get("title", "")
        slide_content = slide.get("content", "") or slide.get("text", "")
        slide_type = slide.get("slide_type", "content")

        logger.info(f"  Generating slide {i}/{slide_count}: {slide_title[:30]}...")

        # Build slide-specific prompt
        slide_prompt = _build_carousel_slide_prompt(
            topic=topic,
            slide_number=i,
            total_slides=slide_count,
            title=slide_title,
            content=slide_content,
            slide_type=slide_type,
            style=style,
            language=language
        )

        # Generate this slide
        result = await _generate_single_slide(slide_prompt, i)

        if result.get("success"):
            image_paths.append(result["image_path"])
            total_cost += result.get("cost_estimate", 0.15)
        else:
            errors.append(f"Slide {i}: {result.get('error', 'Unknown error')}")
            logger.warning(f"  Slide {i} failed: {result.get('error')}")

        # Small delay between requests to avoid rate limiting
        if i < slide_count:
            await asyncio.sleep(1)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Check if we got enough slides
    success = len(image_paths) >= min(3, slide_count)  # At least 3 or all if less

    return {
        "success": success,
        "image_paths": image_paths,
        "slide_count": len(image_paths),
        "requested_count": slide_count,
        "errors": errors,
        "duration": elapsed,
        "cost_estimate": total_cost,
        "model": "fal-ai/nano-banana-pro"
    }


async def _generate_single_slide(prompt: str, slide_number: int) -> Dict[str, Any]:
    """Generate a single carousel slide"""

    try:
        result = await _fal_submit_and_poll(prompt, "square_hd")

        images = result.get("images", [])
        if not images:
            return {"success": False, "error": "No images in fal.ai response"}

        image_url = images[0].get("url")
        if not image_url:
            return {"success": False, "error": "No image URL in fal.ai response"}

        image_path = await _download_fal_image(image_url, f"nano_carousel_{slide_number}")

        # Logo overlay devre dışı - içerikle çakışıyor
        # add_logo_overlay(image_path)

        return {
            "success": True,
            "image_path": image_path,
            "cost_estimate": 0.15
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def _build_infographic_prompt(
    topic: str,
    content_text: str,
    style: str,
    language: str
) -> str:
    """Guide-optimized infographic prompt builder for daily content"""

    lang_instruction = "All text in the image must be in Turkish with proper characters (ğ, ş, ı, ö, ü, ç)." if language == "tr" else "All text should be in English."

    content_summary = content_text[:400] if content_text else f"Key information about {topic}"

    prompt = f"""
{INFOGRAPHIC_STYLE_PROMPT}

CREATE AN INFOGRAPHIC ABOUT: "{topic}"

KEY CONTENT TO VISUALIZE:
{content_summary}

COMPOSITION INSTRUCTIONS:
First, create a bold headline at the top that captures "{topic}" in 3-5 words.
Then, organize the main content into 3-4 visual blocks using icons and short text.
Use curved arrows or flow lines to connect related concepts.
Finally, add a key takeaway or conclusion at the bottom.

STYLE: {style.upper()} - {"Clean minimal with white space" if style == "minimal" else "Modern with subtle gradients" if style == "modern" else "Vibrant and dynamic"}

{lang_instruction}

CRITICAL: Do not include any hashtags, # symbols, or social media tags in the image. This is purely an informational infographic.
"""
    return prompt.strip()


def _build_carousel_slide_prompt(
    topic: str,
    slide_number: int,
    total_slides: int,
    title: str,
    content: str,
    slide_type: str,
    style: str,
    language: str
) -> str:
    """Build prompt for a specific carousel slide"""

    lang_instruction = "Turkish (Türkçe)" if language == "tr" else "English"

    # Slide type specific instructions
    slide_instructions = {
        "cover": "Hero slide with large, impactful typography and minimal elements. This is the first slide - make it attention-grabbing.",
        "content": "Information-rich slide with bullet points, icons, and clear visual hierarchy.",
        "stats": "Data visualization slide with large numbers, charts, or comparison elements.",
        "comparison": "Side-by-side comparison layout with pros/cons or before/after elements.",
        "cta": "Call-to-action slide with @olivenet.io mention and engagement prompt.",
        "summary": "Summary slide with key takeaway and @olivenet.io mention."
    }

    slide_instruction = slide_instructions.get(slide_type, slide_instructions["content"])

    prompt = f"""
{INFOGRAPHIC_STYLE_PROMPT}

CAROUSEL CONTEXT:
- This is slide {slide_number} of {total_slides} in a carousel about: {topic}
- Slide type: {slide_type.upper()}

SLIDE CONTENT:
Title: {title}
Content: {content}

SLIDE-SPECIFIC DESIGN:
{slide_instruction}

STYLE: {style.upper()}
LANGUAGE: {lang_instruction}

Create a cohesive slide that works as part of a carousel series.
Maintain consistent color scheme and design language across all slides.
"""

    return prompt


# Test function
async def test_nano_banana():
    """Test the Nano Banana helper"""

    print("Testing Nano Banana Pro (fal.ai)...")

    result = await generate_infographic(
        topic="LoRaWAN Gateway nedir ve nasil calisir?",
        content_text="IoT cihazlarini internete baglayan kablosuz ag gecidi",
        style="modern",
        use_search=True
    )

    print(f"Result: {result}")
    return result


if __name__ == "__main__":
    asyncio.run(test_nano_banana())
