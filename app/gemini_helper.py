"""
Olivenet Social Media Bot - Gemini 2.5 Flash Image Helper
Generates realistic AI images using Gemini's image generation model.
"""
import aiohttp
import asyncio
import base64
import logging
import os
from datetime import datetime

from .config import settings

logger = logging.getLogger(__name__)


async def generate_realistic_image(topic: str, post_text: str, output_dir: str = "/opt/olivenet-social/outputs") -> str:
    """
    Generate a realistic image using Gemini 2.5 Flash.

    Args:
        topic: Topic in Turkish
        post_text: Post text in Turkish
        output_dir: Output directory for the image

    Returns:
        Path to the generated image file
    """
    # Create English prompt using Claude Code
    english_prompt = await create_image_prompt(topic, post_text)

    logger.info(f"Gemini prompt: {english_prompt}")
    print(f"Gemini prompt: {english_prompt}")

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={settings.gemini_api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": english_prompt}]
            }],
            "generationConfig": {
                "responseModalities": ["image", "text"]
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Gemini API hatasi ({resp.status}): {error_text[:200]}")

                data = await resp.json()

        # Extract image from response
        candidates = data.get("candidates", [])
        if not candidates:
            raise Exception("Gemini yanit dondurmedi")

        parts = candidates[0].get("content", {}).get("parts", [])

        # Find part containing inlineData
        image_data = None
        for part in parts:
            if "inlineData" in part:
                image_data = part["inlineData"]["data"]
                break

        if not image_data:
            raise Exception("Gemini gorsel uretemedi - yanitte gorsel yok")

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Decode base64 and save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gemini_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "wb") as f:
            f.write(base64.b64decode(image_data))

        logger.info(f"Image saved: {filepath}")
        print(f"Gorsel kaydedildi: {filepath}")
        return filepath

    except asyncio.TimeoutError:
        raise Exception("Gemini zaman asimi (120 saniye)")
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        print(f"Gemini hatasi: {e}")
        raise


async def create_image_prompt(topic: str, post_text: str) -> str:
    """
    Create an English image prompt from Turkish topic and text using Claude Code.

    Args:
        topic: Topic in Turkish
        post_text: Post text in Turkish

    Returns:
        English prompt for Gemini
    """
    from .claude_helper import run_claude_code

    prompt = f"""
Turkce konu ve post metnini, AI gorsel uretimi icin Ingilizce prompt'a cevir.

Konu: {topic}
Post metni: {post_text[:300]}

Kurallar:
1. Profesyonel fotograf veya 3D render tarzinda
2. IoT, teknoloji, endustriyel veya tarim temasi
3. Akdeniz/KKTC atmosferi (gunesli, modern, temiz)
4. Anahtar kelimeler ekle: professional, high quality, modern technology, clean aesthetic, detailed
5. Insan yuzu EKLEME (sadece eller veya siluet olabilir)
6. Marka logosu veya yazi EKLEME
7. Sadece Ingilizce prompt yaz, baska aciklama yapma
8. Maksimum 80 kelime, tek paragraf

Konu bazli oneriler:
- Tarim/Sera: greenhouse, plants, sensors, irrigation, sunlight, water droplets
- Enerji: power meters, electrical panels, LED displays, cables, monitoring
- Kestirimci bakim: industrial machinery, gears, sensors, factory floor
- Bina/HVAC: modern building, air conditioning, smart thermostat, office

Ornek cikti:
"Professional photograph of a modern smart greenhouse with IoT sensors monitoring tomato plants, water droplets on green leaves, morning Mediterranean sunlight streaming through glass panels, clean technology aesthetic, high quality, detailed, 8k"
"""

    result = await run_claude_code(prompt, timeout=30)

    # Clean up quotes
    result = result.strip().strip('"').strip("'")

    return result


async def test_gemini_connection() -> dict:
    """Test Gemini API connection."""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={settings.gemini_api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": "A simple green leaf on white background"}]
            }],
            "generationConfig": {
                "responseModalities": ["image", "text"]
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    return {
                        "success": True,
                        "message": "Gemini API baglantisi basarili"
                    }
                else:
                    error = await resp.text()
                    return {
                        "success": False,
                        "message": f"Gemini API hatasi ({resp.status}): {error[:100]}"
                    }
    except Exception as e:
        return {
            "success": False,
            "message": f"Gemini API hatasi: {str(e)}"
        }


async def generate_realistic_image_with_feedback(topic: str, post_text: str, feedback: str, output_dir: str = "/opt/olivenet-social/outputs") -> str:
    """
    Generate a realistic image using Gemini with user feedback.

    Args:
        topic: Topic in Turkish
        post_text: Post text in Turkish
        feedback: User feedback for image modification
        output_dir: Output directory for the image

    Returns:
        Path to the generated image file
    """
    # Create English prompt with feedback using Claude Code
    english_prompt = await create_image_prompt_with_feedback(topic, post_text, feedback)

    logger.info(f"Gemini prompt (with feedback): {english_prompt}")
    print(f"Gemini prompt (with feedback): {english_prompt}")

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={settings.gemini_api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": english_prompt}]
            }],
            "generationConfig": {
                "responseModalities": ["image", "text"]
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Gemini API hatasi ({resp.status}): {error_text[:200]}")

                data = await resp.json()

        # Extract image from response
        candidates = data.get("candidates", [])
        if not candidates:
            raise Exception("Gemini yanit dondurmedi")

        parts = candidates[0].get("content", {}).get("parts", [])

        # Find part containing inlineData
        image_data = None
        for part in parts:
            if "inlineData" in part:
                image_data = part["inlineData"]["data"]
                break

        if not image_data:
            raise Exception("Gemini gorsel uretemedi - yanitte gorsel yok")

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Decode base64 and save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gemini_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "wb") as f:
            f.write(base64.b64decode(image_data))

        logger.info(f"Image saved: {filepath}")
        print(f"Gorsel kaydedildi: {filepath}")
        return filepath

    except asyncio.TimeoutError:
        raise Exception("Gemini zaman asimi (120 saniye)")
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        print(f"Gemini hatasi: {e}")
        raise


async def create_image_prompt_with_feedback(topic: str, post_text: str, feedback: str) -> str:
    """
    Create an English image prompt with user feedback using Claude Code.

    Args:
        topic: Topic in Turkish
        post_text: Post text in Turkish
        feedback: User feedback for image modification

    Returns:
        English prompt for Gemini
    """
    from .claude_helper import run_claude_code

    prompt = f"""
Turkce konu ve geri bildirimi, AI gorsel uretimi icin Ingilizce prompt'a cevir.

Konu: {topic}
Post metni: {post_text[:200]}

KULLANICI GERI BILDIRIMI (MUTLAKA UYGULA):
{feedback}

Kurallar:
1. Geri bildirimi oncelikli olarak uygula
2. Profesyonel fotograf veya 3D render tarzinda
3. IoT, teknoloji temasi
4. Insan yuzu ve marka logosu EKLEME
5. Maksimum 80 kelime, tek paragraf
6. Sadece Ingilizce prompt yaz, baska aciklama yapma
"""

    result = await run_claude_code(prompt, timeout=30)

    # Clean up quotes
    result = result.strip().strip('"').strip("'")

    return result
