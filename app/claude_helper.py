"""
Olivenet Social Media Bot - Claude Code Helper
Claude Code CLI wrapper for AI-powered content generation.
"""
import asyncio
import logging
import re
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)


async def run_claude_code(prompt: str, timeout: int = 60) -> str:
    """
    Run Claude Code CLI with the given prompt.

    Args:
        prompt: The prompt to send to Claude Code
        timeout: Maximum execution time in seconds

    Returns:
        Claude's response as a string

    Raises:
        Exception: If timeout occurs or Claude Code fails
    """
    try:
        process = await asyncio.create_subprocess_exec(
            'claude', '-p', prompt, '--print',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(settings.base_dir)
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8').strip()
            logger.error(f"Claude Code error: {error_msg}")
            raise Exception(f"Claude Code failed: {error_msg}")

        result = stdout.decode('utf-8').strip()
        logger.info(f"Claude Code response received ({len(result)} chars)")
        return result

    except asyncio.TimeoutError:
        if process:
            process.kill()
        logger.error(f"Claude Code timeout after {timeout}s")
        raise Exception(f"Claude Code timeout ({timeout}s)")
    except FileNotFoundError:
        logger.error("Claude Code CLI not found")
        raise Exception("Claude Code CLI not found. Is it installed?")


async def generate_post_text(topic: str) -> str:
    """
    Generate social media post text using Claude Code.

    Args:
        topic: The topic/subject for the post

    Returns:
        Generated post text in Turkish
    """
    prompt = f"""
/opt/olivenet-social/context/ klasorundeki dosyalari oku:
- company-profile.md (sirket bilgileri, ton, hashtag'ler)
- content-strategy.md (post turleri, emoji kullanimi)

Konu: {topic}

Bu konuda bir Facebook/Instagram postu yaz:
- Turkce
- 2-3 paragraf
- Emoji kullan (ama abartma, 5-7 emoji max)
- Hashtag'ler ekle (5-7 tane, #Olivenet #KKTC #IoT mutlaka olsun)
- CTA (call-to-action) ekle
- Profesyonel ama samimi ton

SADECE post metnini yaz, baska aciklama yapma.
"""

    logger.info(f"Generating post text for topic: {topic}")
    result = await run_claude_code(prompt, timeout=settings.claude_timeout_post)

    # Clean up any potential markdown artifacts
    result = clean_response(result)

    return result


async def generate_visual_html(post_text: str, topic: str) -> str:
    """
    Generate HTML code for social media visual using Claude Code.

    Args:
        post_text: The post text to create a visual for
        topic: The topic/subject for context

    Returns:
        Complete HTML code for the visual (1080x1080px)
    """
    # Truncate post text if too long to avoid prompt issues
    short_post = post_text[:500] if len(post_text) > 500 else post_text

    # Logo base64 verisini oku
    try:
        from app.logo_data import LOGO_BASE64
        logo_img = LOGO_BASE64.strip()
    except Exception:
        logo_img = ""

    prompt = f"""
/opt/olivenet-social/context/visual-guidelines.md dosyasini oku.

Bu post icin 1080x1080px sosyal medya gorseli HTML'i olustur:

Post metni: {short_post[:300]}
Konu: {topic}

## TASARIM KURALLARI:

0. FONT (zorunlu):
   - External font KULLANMA (Google Fonts, vb.)
   - System font kullan: font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
   - Ya da: font-family: system-ui, sans-serif;

1. RENK PALETİ (zorunlu):
   - Arka plan: Koyu gradient (#0a0a0a, #1a2e1a)
   - Ana vurgu: Olive yeşil (#4a7c4a)
   - Accent: Sky mavi (#0ea5e9) veya Violet (#8b5cf6)
   - Metin: Beyaz ve gri tonları

2. STİL:
   - Glassmorphism kartlar (backdrop-filter: blur)
   - Köşelerde dekoratif renkli noktalar
   - Grid pattern arka plan (opsiyonel)
   - Modern, minimal, profesyonel

3. SOL ALT KÖŞE - LOGO (zorunlu):
   - Bu base64 logo resmini kullan: {{{{logo}}}}
   - Logo ve yazı yan yana olacak:
   ```
   <div style="position:absolute;bottom:24px;left:24px;display:flex;align-items:center;gap:12px;">
     <img src="{{{{logo}}}}" style="width:48px;height:48px;border-radius:8px;">
     <span style="color:#ffffff;font-size:24px;font-weight:600;font-family:system-ui,sans-serif;">Olivenet</span>
   </div>
   ```

4. SAĞ ALT KÖŞE:
   - Hashtag YAZMA (bunlar post metninde olacak)
   - Boş bırak veya minimal dekoratif element

5. YARATICILIK (önemli):
   - Her görsel farklı layout dene
   - Bazen tek büyük metrik, bazen grid
   - Bazen ilustrasyon/ikon ağırlıklı, bazen data-driven
   - Sıkıcı ve tekrarlayan olma
   - Konuya özel yaratıcı elementler ekle:
     * Tarım: yaprak, damla, toprak ikonları
     * Enerji: şimşek, güneş, pil ikonları
     * Kestirimci bakım: dişli, grafik, kalp atışı
     * Bina: ev, termometre, hava ikonları
   - SVG ikonlar kullanabilirsin (inline)

6. İÇERİK:
   - Dikkat çekici başlık
   - 1-2 anahtar metrik/istatistik
   - Konuyla ilgili görsel element

SADECE HTML kodunu yaz. Markdown code block (```) KULLANMA.
Aciklama yazma, direkt <!DOCTYPE html> ile basla.
HTML icinde {{{{logo}}}} placeholder'i kullan, ben degistirecegim.
"""

    logger.info(f"Generating visual HTML for topic: {topic}")
    result = await run_claude_code(prompt, timeout=settings.claude_timeout_visual)

    # Clean up and extract HTML
    result = extract_html(result)

    # Logo placeholder'ı gerçek base64 ile değiştir
    if logo_img and "{{logo}}" in result:
        result = result.replace("{{logo}}", logo_img)

    return result


def clean_response(text: str) -> str:
    """Remove markdown artifacts and clean up response."""
    # Remove code blocks if present
    text = re.sub(r'^```\w*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n?```$', '', text, flags=re.MULTILINE)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def extract_html(text: str) -> str:
    """Extract HTML content from response, handling various formats."""
    text = text.strip()

    # Remove markdown code blocks if present
    if text.startswith('```'):
        # Find the end of the opening tag
        first_newline = text.find('\n')
        if first_newline != -1:
            text = text[first_newline + 1:]
        # Remove closing ```
        if text.endswith('```'):
            text = text[:-3]

    text = text.strip()

    # Ensure it starts with DOCTYPE or html tag
    if not text.lower().startswith('<!doctype') and not text.lower().startswith('<html'):
        # Try to find HTML content
        html_match = re.search(r'(<!DOCTYPE html>.*</html>)', text, re.IGNORECASE | re.DOTALL)
        if html_match:
            text = html_match.group(1)
        else:
            # Wrap in basic HTML structure
            text = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Olivenet Social</title>
</head>
<body>
{text}
</body>
</html>"""

    return text


async def improve_post_text(original_post: str, feedback: str) -> str:
    """
    Improve an existing post based on feedback.

    Args:
        original_post: The original post text
        feedback: User feedback for improvement

    Returns:
        Improved post text
    """
    prompt = f"""
Asagidaki sosyal medya postunu gelistir.

Mevcut post:
{original_post}

Geri bildirim/istek:
{feedback}

Kurallari koru:
- Turkce
- Emoji kullan (abartma)
- Hashtag'ler olsun
- CTA ekle

SADECE yeni post metnini yaz, aciklama yapma.
"""

    logger.info("Improving post text based on feedback")
    result = await run_claude_code(prompt, timeout=settings.claude_timeout_post)
    return clean_response(result)
