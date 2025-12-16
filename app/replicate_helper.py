"""
Olivenet Social Media Bot - Replicate Flux Helper
Generates realistic AI images using Replicate's Flux model.
"""
import asyncio
import logging
import os
from datetime import datetime

import aiohttp
import replicate

from .config import settings

logger = logging.getLogger(__name__)


async def generate_realistic_image(topic: str, post_text: str, output_dir: str = "/opt/olivenet-social/outputs") -> str:
    """
    Generate a realistic image using Replicate Flux.

    Args:
        topic: Topic in Turkish
        post_text: Post text in Turkish
        output_dir: Output directory for the image

    Returns:
        Path to the generated image file
    """
    # Set Replicate API token
    os.environ["REPLICATE_API_TOKEN"] = settings.replicate_api_token

    # Create English prompt using Claude Code
    english_prompt = await create_image_prompt(topic, post_text)

    logger.info(f"Flux prompt: {english_prompt}")
    print(f"Flux prompt: {english_prompt}")

    try:
        # Generate image with Flux Schnell model (fast and high quality)
        output = await asyncio.to_thread(
            replicate.run,
            "black-forest-labs/flux-schnell",
            input={
                "prompt": english_prompt,
                "num_outputs": 1,
                "aspect_ratio": "1:1",
                "output_format": "png",
                "output_quality": 90
            }
        )

        if output and len(output) > 0:
            image_url = output[0]
            logger.info(f"Image URL: {image_url}")
            print(f"Gorsel URL: {image_url}")

            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)

            # Download the image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"flux_{timestamp}.png"
            filepath = os.path.join(output_dir, filename)

            async with aiohttp.ClientSession() as session:
                async with session.get(str(image_url)) as resp:
                    if resp.status == 200:
                        with open(filepath, 'wb') as f:
                            f.write(await resp.read())

            logger.info(f"Image saved: {filepath}")
            print(f"Gorsel kaydedildi: {filepath}")
            return filepath
        else:
            raise Exception("Flux could not generate image")

    except Exception as e:
        logger.error(f"Replicate error: {e}")
        print(f"Replicate hatasi: {e}")
        raise


async def create_image_prompt(topic: str, post_text: str) -> str:
    """
    Create an English image prompt from Turkish topic and text using Claude Code.

    Args:
        topic: Topic in Turkish
        post_text: Post text in Turkish

    Returns:
        English prompt for Flux
    """
    from .claude_helper import run_claude_code

    prompt = f"""
Turkce konu ve post metnini, Flux AI icin Ingilizce gorsel prompt'una cevir.

Konu: {topic}
Post metni: {post_text[:300]}

Kurallar:
1. Profesyonel fotograf tarzinda olsun
2. IoT, teknoloji, endustriyel tema
3. KKTC/Akdeniz atmosferi (gunesli, modern)
4. Su anahtar kelimeleri ekle: professional photography, 8k, photorealistic, modern technology, clean aesthetic
5. Insan yuzu veya marka logosu EKLEME
6. Sadece Ingilizce prompt yaz, baska bir sey yazma
7. Maksimum 100 kelime

Ornek cikti formati:
"Professional photograph of a modern smart greenhouse in Mediterranean setting, IoT sensors monitoring plants, water droplets on leaves, morning sunlight, clean technology aesthetic, 8k, photorealistic"
"""

    result = await run_claude_code(prompt, timeout=30)

    # Clean up quotes
    result = result.strip().strip('"').strip("'")

    return result


async def test_replicate_connection() -> dict:
    """Test Replicate API connection."""
    try:
        os.environ["REPLICATE_API_TOKEN"] = settings.replicate_api_token

        # Simple model list check
        models = replicate.models.list()

        return {
            "success": True,
            "message": "Replicate API baglantisi basarili"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Replicate API hatasi: {str(e)}"
        }
