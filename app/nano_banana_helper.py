"""
Nano Banana Pro - Gemini Image Generation for Infographics
Model: gemini-3-pro-image-preview
- Text rendering %94 accuracy
- Google Search grounding (real-time data)
- Infographic, diagram, arrow-box visuals
"""

import os
import asyncio
import base64
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("nano_banana")

GEMINI_API_KEY = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
OUTPUT_DIR = str(settings.outputs_dir)

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

# Google GenAI client
_client = None


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


def get_client():
    """Get Google GenAI client (singleton)"""
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


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
        resolution: Image size (1K, 2K, 4K)
        use_search: Enable Google Search grounding for real-time data

    Returns:
        Dict with success, image_path, error, etc.
    """

    if not GEMINI_API_KEY:
        return {"success": False, "error": "GEMINI_API_KEY not configured"}

    start_time = datetime.now()

    # Build the prompt
    prompt = _build_infographic_prompt(topic, content_text, style, language)

    logger.info(f"Nano Banana infographic generation starting...")
    logger.info(f"  Topic: {topic[:50]}...")
    logger.info(f"  Style: {style}, Aspect: {aspect_ratio}, Resolution: {resolution}")

    try:
        from google.genai import types

        client = get_client()

        # Build config with optional Google Search grounding
        tools = []
        if use_search:
            tools.append({"google_search": {}})

        config = types.GenerateContentConfig(
            response_modalities=['TEXT', 'IMAGE'],
            tools=tools if tools else None,
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=resolution
            )
        )

        # Generate content
        logger.info("  Sending request to Nano Banana Pro API...")

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=prompt,
            config=config
        )

        # Process response
        image_path = None
        text_response = ""

        for part in response.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                # Save image
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                image_path = f"{OUTPUT_DIR}/nano_banana_{timestamp}.png"

                image = part.as_image()
                image.save(image_path)

                # Logo overlay devre dışı - içerikle çakışıyor
                # add_logo_overlay(image_path)

                file_size = os.path.getsize(image_path)
                logger.info(f"  Image saved: {image_path} ({file_size/1024:.1f} KB)")

            elif hasattr(part, 'text') and part.text:
                text_response = part.text

        if not image_path:
            return {"success": False, "error": "No image generated in response"}

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "image_path": image_path,
            "file_size": os.path.getsize(image_path),
            "duration": elapsed,
            "text_response": text_response,
            "model": "gemini-3-pro-image-preview",
            "cost_estimate": 0.15  # ~$0.15 per image
        }

    except ImportError as e:
        logger.error(f"google-genai package missing: {e}")
        return {"success": False, "error": f"google-genai package missing: {e}"}

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

    if not GEMINI_API_KEY:
        return {"success": False, "error": "GEMINI_API_KEY not configured"}

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
        "model": "gemini-3-pro-image-preview"
    }


async def _generate_single_slide(prompt: str, slide_number: int) -> Dict[str, Any]:
    """Generate a single carousel slide"""

    try:
        from google.genai import types

        client = get_client()

        config = types.GenerateContentConfig(
            response_modalities=['TEXT', 'IMAGE'],
            tools=[{"google_search": {}}],
            image_config=types.ImageConfig(
                aspect_ratio="1:1",
                image_size="1K"
            )
        )

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=prompt,
            config=config
        )

        # Find and save image
        for part in response.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                image_path = f"{OUTPUT_DIR}/nano_carousel_{timestamp}_{slide_number}.png"

                image = part.as_image()
                image.save(image_path)

                # Logo overlay devre dışı - içerikle çakışıyor
                # add_logo_overlay(image_path)

                return {
                    "success": True,
                    "image_path": image_path,
                    "cost_estimate": 0.15
                }

        return {"success": False, "error": "No image in response"}

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
        "cta": "Call-to-action slide with @olivenet.io mention and engagement prompt."
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

    print("Testing Nano Banana Pro...")

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
