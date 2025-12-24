"""
Olivenet Social Media Bot - Claude Code Helper
Claude Code CLI wrapper for AI-powered content generation.
"""
import asyncio
import base64
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict

from .config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# OLIVENET WEBSITE TASARIM SİSTEMİ
# Website (/opt/olivenet-website) ile tutarlılık için kullanılacak sabitler
# Kaynak: globals.css, Stats.tsx, FeaturesGrid.tsx, CTABanner.tsx
# =============================================================================
OLIVENET_DESIGN = {
    "colors": {
        # Olive Palette (website globals.css:64-76)
        "olive_900": "#1a2e1a",
        "olive_800": "#243524",
        "olive_700": "#2d4a2d",
        "olive_600": "#3a5f3a",
        "olive_500": "#4a7c4a",
        "olive_400": "#5e9a5e",
        "olive_300": "#7ab87a",
        "olive_200": "#a3d4a3",
        "olive_100": "#d1e8d1",
        "olive_50": "#e8f4e8",
        # Sky Accent (website globals.css:78-80)
        "sky_500": "#0ea5e9",
        "sky_400": "#38bdf8",
        "sky_300": "#7dd3fc",
        # Backgrounds
        "bg_light": "#ffffff",
        "bg_dark": "#0a0a0a",
        "card_dark": "#171717",
        # Text
        "text_primary_dark": "#fafafa",
        "text_muted_dark": "#a3a3a3",
    },
    "fonts": {
        "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "heading_weight": "700",
        "body_weight": "400",
    },
    "sizes": {
        "h1": "80px",      # Eski: 48px - Mobil okunurluk için artırıldı
        "h2": "56px",      # Eski: 36px
        "h3": "40px",      # Eski: 24px
        "body": "32px",    # Eski: 18px
        "small": "24px",   # Eski: 14px
    },
    "radius": {
        "base": "10px",
        "card": "16px",
        "cta": "24px",
        "button": "8px",
        "icon": "12px",
    },
    "gradients": {
        "primary": "linear-gradient(to bottom right, #2d4a2d, #1a2e1a)",
        "cta": "linear-gradient(to bottom right, #3a5f3a, #1a2e1a)",
        "accent": "linear-gradient(to right, #4a7c4a, #0ea5e9)",
    },
    "effects": {
        "glass": "background: rgba(255,255,255,0.1); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.2);",
        "grid_pattern": "background-image: linear-gradient(to right, rgba(74,124,74,0.1) 1px, transparent 1px), linear-gradient(to bottom, rgba(74,124,74,0.1) 1px, transparent 1px); background-size: 40px 40px;",
    }
}


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
    Uses social media expert analysis for better engagement.

    Args:
        topic: The topic/subject for the post

    Returns:
        Generated post text in Turkish
    """
    prompt = f"""
/opt/olivenet-social-bot/context/ klasorundeki TUM dosyalari oku:
- company-profile.md (sirket bilgileri)
- content-strategy.md (icerik stratejisi)
- social-media-expert.md (sosyal medya uzmanligi - ONEMLI!)

## GOREV: Sosyal Medya Uzmani Olarak Dusun

Konu: {topic}

### ADIM 1: ANALIZ (icinden gec)
Once sunlari dusun:
- Bu konu KKTC'deki hedef kitleyi neden ilgilendirsin?
- Hangi duygusal tetikleyici en etkili olur? (FOMO, korku, umut, merak)
- Hook nasil olmali? (Soru, istatistik, sok edici bilgi?)
- Sosyal medya expert rehberindeki basari faktorlerinden hangileri uygulanabilir?

### ADIM 2: POST URET
Analiz sonucuna gore Facebook postu yaz:

Kurallar:
- Ilk cumle HOOK olmali (scroll durdurucu)
- Turkce, samimi ama profesyonel ton
- Maksimum 3-4 kisa paragraf
- Emoji kullan ama abartma (3-5 emoji)
- Somut fayda veya rakam icersin
- CTA (call-to-action) ekle
- Hashtag'ler ekle (#Olivenet #KKTC + konuya ozel 2-3 tane)

### ADIM 3: KENDINI DEGERLENDIR
Post'u urettikten sonra kontrol et:
- Hook Test: Ilk cumle dikkat cekiyor mu?
- Deger Test: Okuyucu ne kazaniyor?
- KKTC Test: Yerel isletme sahibi ilgilenir mi?

Eger herhangi bir test basarisizsa, post'u revize et.

### CIKTI
SADECE final post metnini yaz.
Analiz veya degerlendirme notlarini YAZMA.
"""

    logger.info(f"Generating post text for topic: {topic}")
    result = await run_claude_code(prompt, timeout=settings.claude_timeout_post)

    # Clean up any potential markdown artifacts
    result = clean_response(result)

    return result

async def suggest_topics() -> dict:
    """
    Generate topic suggestions like a social media expert.
    Considers current season and day of week.

    Returns:
        Dictionary with topics list: {"topics": [{"title": ..., "reason": ..., "hook": ..., "engagement": ...}, ...]}
    """
    import json
    from datetime import datetime

    today = datetime.now()
    day_names = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
    day_name = day_names[today.weekday()]
    month = today.month

    # Determine season
    if month in [12, 1, 2]:
        season = "kis"
        season_themes = "enerji tasarrufu, isitma maliyetleri, kis bakimi"
    elif month in [3, 4, 5]:
        season = "ilkbahar"
        season_themes = "ekim donemi, sera hazirligi, yeni sezon"
    elif month in [6, 7, 8]:
        season = "yaz"
        season_themes = "su tasarrufu, sera sogutma, yuksek sicaklik"
    else:
        season = "sonbahar"
        season_themes = "hasat donemi, verim analizi, kis hazirligi"

    prompt = f"""
/opt/olivenet-social-bot/context/social-media-expert.md dosyasini oku.
/opt/olivenet-social-bot/context/company-profile.md dosyasini oku.

## GOREV: Sosyal Medya Stratejisti Olarak Konu Oner

Bugun: {day_name}
Mevsim: {season}
Mevsimsel temalar: {season_themes}

Olivenet icin bugun paylasilabilecek 3 farkli post konusu oner.

Oneriler farkli kategorilerden olsun:
- Biri egitici/bilgilendirici
- Biri duygusal/hikaye
- Biri pratik ipucu

## KRITIK: JSON FORMATI
SADECE asagidaki JSON formatinda cevap ver, baska bir sey YAZMA:

{{"topics": [
  {{"title": "Konu basligi kisa", "reason": "Neden bugun 1 cumle", "hook": "Hook onerisi ilk cumle", "engagement": "yuksek"}},
  {{"title": "Ikinci konu", "reason": "Neden", "hook": "Hook", "engagement": "orta"}},
  {{"title": "Ucuncu konu", "reason": "Neden", "hook": "Hook", "engagement": "yuksek"}}
]}}

SADECE JSON yaz, markdown code block (```) KULLANMA!
"""

    logger.info("Generating topic suggestions")
    result = await run_claude_code(prompt, timeout=60)
    result = clean_response(result)

    # Parse JSON response
    try:
        # Remove any markdown artifacts
        result = result.strip()
        if result.startswith('```'):
            result = result.split('\n', 1)[1]
        if result.endswith('```'):
            result = result.rsplit('```', 1)[0]
        result = result.strip()

        data = json.loads(result)
        logger.info(f"Parsed {len(data.get('topics', []))} topic suggestions")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse topic suggestions JSON: {e}")
        # Return a fallback structure
        return {
            "topics": [
                {"title": "IoT ile Enerji Tasarrufu", "reason": "Kis mevsiminde enerji maliyetleri artar", "hook": "Elektrik faturanizi %30 dusurmenin sirri", "engagement": "yuksek"},
                {"title": "Akilli Sera Otomasyonu", "reason": "Teknoloji ilgi ceker", "hook": "Seraniz siz uyurken bile calissin!", "engagement": "orta"},
                {"title": "KKTC'de Dijital Donusum", "reason": "Yerel baglam onemli", "hook": "Kibris'ta isletmenizi nasil dijitallestirirsiniz?", "engagement": "yuksek"}
            ],
            "error": "JSON parse failed, using fallback"
        }

# =============================================================================
# BILLBOARD INFOGRAPHIC İKONLARI
# =============================================================================
BILLBOARD_ICONS = {
    "cpu": '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>',
    "chart": '<svg viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
    "leaf": '<svg viewBox="0 0 24 24"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/></svg>',
    "bolt": '<svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    "shield": '<svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    "wifi": '<svg viewBox="0 0 24 24"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>',
    "gear": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    "cloud": '<svg viewBox="0 0 24 24"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>',
    "trending": '<svg viewBox="0 0 24 24"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
    "sun": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>',
    # Dashboard template icons
    "thermometer": '<svg viewBox="0 0 24 24"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/></svg>',
    "droplet": '<svg viewBox="0 0 24 24"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>',
    "gauge": '<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5 3.56"/><path d="M12 2v8l4.5 4.5"/></svg>',
    "wind": '<svg viewBox="0 0 24 24"><path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/></svg>',
    # Comparison template icons
    "radio": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"/></svg>',
    "signal": '<svg viewBox="0 0 24 24"><path d="M2 20h.01"/><path d="M7 20v-4"/><path d="M12 20v-8"/><path d="M17 20V8"/><path d="M22 4v16"/></svg>',
    "bluetooth": '<svg viewBox="0 0 24 24"><polyline points="6.5 6.5 17.5 17.5 12 23 12 1 17.5 6.5 6.5 17.5"/></svg>',
    "satellite": '<svg viewBox="0 0 24 24"><path d="M13 7 9 3 5 7l4 4"/><path d="m17 11 4 4-4 4-4-4"/><path d="m8 12 4 4 6-6-4-4-6 6"/><path d="m16 8 3-3"/><path d="M9 21a6 6 0 0 0-6-6"/></svg>',
    "network": '<svg viewBox="0 0 24 24"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/></svg>',
    # Process template icons
    "settings": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    "download": '<svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    "link": '<svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
    "check": '<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>',
    "play": '<svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
    # Quote template icons
    "lightbulb": '<svg viewBox="0 0 24 24"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>',
    "quote": '<svg viewBox="0 0 24 24"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21c0 1 0 1 1 1z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/></svg>',
    "star": '<svg viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    "info": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    "target": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
    "rocket": '<svg viewBox="0 0 24 24"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>',
    "building": '<svg viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/></svg>'
}

def get_icon_svg(icon_type: str) -> str:
    """Get SVG code for an icon type"""
    return BILLBOARD_ICONS.get(icon_type, BILLBOARD_ICONS["cpu"])


async def generate_infographic_data(post_text: str, topic: str) -> dict:
    """
    Billboard style infografik için sadece JSON veri üret.

    Args:
        post_text: Post metni
        topic: Konu

    Returns:
        dict: {hero_stat, hero_text, icon_type, variant}
    """
    import json

    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için BILLBOARD STYLE infografik verisi üret.

KURALLAR:
- hero_stat: TEK büyük rakam veya yüzde. Örnekler: "%90", "3x", "2024", "₺50K", "24/7", "10M+"
- hero_text: MAKSİMUM 8 KELİME, tek kısa cümle. Türkçe olmalı.
- icon_type: cpu, chart, leaf, bolt, shield, wifi, gear, cloud, trending, sun
- variant: Konuya göre renk varyantı seç:
  * tarim: Tarım, sera, bitki, hasat konuları (yeşil)
  * enerji: Enerji, elektrik, güneş, pil konuları (sarı)
  * bakim: Bakım, arıza, kestirimci konular (mor)
  * bina: Bina, HVAC, klima, ısıtma konuları (mavi)
  * default: Genel IoT, teknoloji konuları (yeşil)

SADECE geçerli JSON döndür, başka hiçbir şey yazma:
{{"hero_stat": "...", "hero_text": "...", "icon_type": "...", "variant": "..."}}
"""

    logger.info(f"Generating infographic data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)

        # JSON'u çıkar
        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)

        # JSON parse
        data = json.loads(result)

        # Doğrulama
        required_keys = ["hero_stat", "hero_text", "icon_type", "variant"]
        for key in required_keys:
            if key not in data:
                data[key] = "default" if key == "variant" else "N/A"

        return data

    except Exception as e:
        logger.error(f"Infographic data generation error: {e}")
        # Fallback
        return {
            "hero_stat": "%100",
            "hero_text": "Akıllı çözümlerle geleceğe hazır olun",
            "icon_type": "cpu",
            "variant": "default"
        }


async def generate_billboard_html(post_text: str, topic: str) -> str:
    """
    Billboard style infografik HTML üret.
    JSON veri al, sabit template'e yerleştir.
    """
    import os

    # JSON veri al
    data = await generate_infographic_data(post_text, topic)

    # Template'i oku
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "billboard-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Logo data'yı al
    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logger.warning("logo_data.py bulunamadı, placeholder kullanılıyor")
        logo_data = ""

    # Placeholder'ları değiştir
    html = html.replace("{{HERO_STAT}}", data.get("hero_stat", "%100"))
    html = html.replace("{{HERO_TEXT}}", data.get("hero_text", "Akıllı çözümler"))
    html = html.replace("{{ICON_SVG}}", get_icon_svg(data.get("icon_type", "cpu")))
    html = html.replace("{{VARIANT}}", data.get("variant", ""))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    logger.info(f"Billboard infographic generated: stat={data.get('hero_stat')}, variant={data.get('variant')}")

    return html


async def generate_visual_html(post_text: str, topic: str) -> str:
    """
    Generate HTML code for social media visual using Claude Code.

    NOT: Bu fonksiyon artık billboard style kullanıyor.

    Args:
        post_text: The post text to create a visual for
        topic: The topic/subject for context

    Returns:
        Complete HTML code for the visual (1080x1080px)
    """
    # Billboard style kullan
    return await generate_billboard_html(post_text, topic)


async def generate_visual_html_legacy(post_text: str, topic: str) -> str:
    """
    LEGACY: Generate HTML code for social media visual using Claude Code.
    Eski karmaşık template için kullanılıyordu, artık kullanılmıyor.

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
/opt/olivenet-social-bot/context/visual-guidelines.md dosyasini oku.

Bu post icin 1080x1080px sosyal medya gorseli HTML'i olustur:

Post metni: {short_post[:300]}
Konu: {topic}

## TASARIM SİSTEMİ (Website ile Tutarlı):

### RENK PALETİ (zorunlu - website globals.css'den):
OLIVE PALETİ:
- olive-900: #1a2e1a (en koyu, arka plan gradient)
- olive-700: #2d4a2d (primary, gradient başlangıç)
- olive-500: #4a7c4a (ana vurgu rengi)
- olive-400: #5e9a5e (hover, açık vurgu)
- olive-200: #a3d4a3 (label, açık metin)
- olive-50:  #e8f4e8 (highlight, arka plan açık)

SKY ACCENT:
- sky-500: #0ea5e9 (accent)
- sky-400: #38bdf8 (accent parlak)

ARKA PLAN & METİN:
- Arka plan gradient: #0a0a0a → #1a2e1a
- Metin birincil: #fafafa (beyaz)
- Metin ikincil: #a3a3a3 (gri)

### TİPOGRAFİ (zorunlu):
- Font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif
- Başlık: 48px, font-weight: 700, letter-spacing: -0.02em
- Alt başlık: 24px, font-weight: 600
- Body: 18px, font-weight: 400, line-height: 1.6

### BORDER RADIUS (website tutarlılığı):
- Card/Container: 16px (rounded-2xl)
- Button: 8px
- Icon container: 12px
- CTA box: 24px

### BILEŞEN STİLLERİ:

1. STATS BOX (büyük rakam gösterimi - website Stats.tsx):
   background: #1a2e1a;
   Rakam: 48-64px, bold, #ffffff
   Label: 14px, #a3d4a3
   Border-radius: 16px
   Padding: 24px

2. FEATURE CARD (website FeaturesGrid.tsx):
   background: rgba(255,255,255,0.05);
   border: 1px solid rgba(255,255,255,0.1);
   border-radius: 16px;
   padding: 24px;

3. ICON CONTAINER:
   width: 48px; height: 48px;
   background: rgba(74,124,74,0.1);
   border-radius: 12px;
   İkon rengi: #4a7c4a

4. GLASS EFFECT:
   background: rgba(255,255,255,0.1);
   backdrop-filter: blur(12px);
   border: 1px solid rgba(255,255,255,0.2);

5. GRID PATTERN (opsiyonel):
   background-image: linear-gradient(to right, rgba(74,124,74,0.1) 1px, transparent 1px),
                     linear-gradient(to bottom, rgba(74,124,74,0.1) 1px, transparent 1px);
   background-size: 40px 40px;

### SOL ALT KÖŞE - LOGO (zorunlu):
<div style="position:absolute;bottom:24px;left:24px;display:flex;align-items:center;gap:12px;">
  <img src="{{{{logo}}}}" style="width:48px;height:48px;border-radius:8px;">
  <span style="color:#ffffff;font-size:24px;font-weight:600;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">Olivenet</span>
</div>

### SAĞ ALT KÖŞE:
- Hashtag YAZMA (post metninde olacak)
- Boş bırak veya minimal dekoratif element

### YARATICILIK (önemli):
- Her görsel farklı layout dene
- Bazen tek büyük metrik (Stats Box stili), bazen grid
- Konuya özel SVG ikonlar:
  * Tarım: yaprak, damla, toprak
  * Enerji: şimşek, güneş, pil
  * Kestirimci bakım: dişli, grafik
  * Bina: ev, termometre

### İÇERİK:
- Dikkat çekici başlık
- 1-2 anahtar metrik/istatistik
- Konuyla ilgili görsel element

### CRITICAL SPELLING RULES:
- "Olivenet" - NOT "Ovenet", "Oivenet", "Olivnet"
- "LoRaWAN" - NOT "Lorawan", "LoraWAN", "Lorwan"
- "IoT" - NOT "Iot", "IOT", "lot"
- "KKTC" - NOT "Kktc", "kktc"
Double-check ALL brand names and technical terms!

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

async def generate_visual_html_with_feedback(post_text: str, topic: str, feedback: str) -> str:
    """
    Generate HTML code for social media visual with user feedback.

    Args:
        post_text: The post text to create a visual for
        topic: The topic/subject for context
        feedback: User feedback for visual modification

    Returns:
        Complete HTML code for the visual (1080x1080px)
    """
    short_post = post_text[:500] if len(post_text) > 500 else post_text

    try:
        from app.logo_data import LOGO_BASE64
        logo_img = LOGO_BASE64.strip()
    except Exception:
        logo_img = ""

    prompt = f"""
/opt/olivenet-social-bot/context/visual-guidelines.md dosyasini oku.

Bu post icin 1080x1080px sosyal medya gorseli HTML'i olustur:

Post metni: {short_post[:300]}
Konu: {topic}

KULLANICI GERI BILDIRIMI (ONCELIKLI - MUTLAKA UYGULA):
{feedback}

## TASARIM KURALLARI:

0. FONT (zorunlu):
   - System font kullan: font-family: system-ui, sans-serif;

1. RENK PALETI:
   - Arka plan: Koyu gradient (#0a0a0a, #1a2e1a)
   - Ana vurgu: Olive yesil (#4a7c4a)
   - Accent: Sky mavi (#0ea5e9) veya Violet (#8b5cf6)

2. STIL:
   - Glassmorphism kartlar
   - Modern, minimal, profesyonel
   - Cok fazla metin KOYMA - ozet ve gorsel agirlikli

3. SOL ALT KOSE - LOGO:
   <div style="position:absolute;bottom:24px;left:24px;display:flex;align-items:center;gap:12px;">
     <img src="{{{{logo}}}}" style="width:48px;height:48px;border-radius:8px;">
     <span style="color:#ffffff;font-size:24px;font-weight:600;">Olivenet</span>
   </div>

4. SAG ALT KOSE: Bos birak (hashtag yok)

5. YARATICILIK:
   - Her gorsel farkli layout dene
   - Sikici ve tekrarlayan olma

SADECE HTML kodunu yaz. Markdown code block (```) KULLANMA.
Aciklama yazma, direkt <!DOCTYPE html> ile basla.
HTML icinde {{{{logo}}}} placeholder'i kullan.
"""

    logger.info(f"Generating visual HTML with feedback for topic: {topic}")
    result = await run_claude_code(prompt, timeout=120)

    result = extract_html(result)

    if logo_img and "{{logo}}" in result:
        result = result.replace("{{logo}}", logo_img)

    return result


async def generate_video_prompt(post_text: str, topic: str) -> str:
    """
    Claude Code ile Veo 3 için profesyonel video prompt'u üret.

    Args:
        post_text: Türkçe post metni
        topic: Konu

    Returns:
        İngilizce video prompt
    """
    short_post = post_text[:400] if len(post_text) > 400 else post_text

    prompt = f"""
## GÖREV: Veo 3 Video Prompt Mühendisliği

Post metni (Türkçe): {short_post}
Konu: {topic}

Sen bir profesyonel video prompt mühendisisin. Google Veo 3 için mükemmel bir video prompt'u yazacaksın.

### VEO 3 PROMPT KURALLARI:

1. **DİL**: Mutlaka İNGİLİZCE yaz

2. **YAPI** (Bu sırayla):
   - Kamera hareketi (örn: "Slow cinematic dolly shot", "Aerial drone view")
   - Ana sahne açıklaması
   - Işıklandırma (örn: "soft natural lighting", "cool blue tech lighting")
   - Renk paleti (Olivenet: olive green #4a7c4a, sky blue #38bdf8)
   - Atmosfer/mood
   - Detaylar ve aksiyon

3. **OLIVENET MARKA KİMLİĞİ**:
   - Renk paleti: Olive green ve sky blue tonları
   - Profesyonel ama samimi
   - Teknoloji + doğa birleşimi
   - Modern, temiz, minimal

4. **KONUYA GÖRE GÖRSEL TEMALAR**:

   AKILLI TARIM / SERA:
   - Yeşil seralar, bitkiler, damla sulama
   - Sensörler toprakta/yapraklarda
   - Güneş ışığı, doğal ortam
   - Su damlacıkları, büyüme

   ENERJİ İZLEME:
   - Elektrik sayaçları, LED göstergeler
   - Veri akışı görselleştirmesi
   - Fabrika/tesis ortamı
   - Dashboard ekranlar

   KESTİRİMCİ BAKIM:
   - Endüstriyel makineler, dişliler
   - Sensörler, kablolar
   - Diagnostik ekranlar

   BİNA OTOMASYONU:
   - Modern ofis/bina içi
   - Akıllı termostatlar, ışık kontrol

5. **TEKNİK DETAYLAR**:
   - 5 saniyelik video için yeterli hareket
   - Çok karmaşık sahneler YAPMA
   - Tek bir güçlü görsel konsept
   - Tek sürekli sahne

6. **YASAKLAR**:
   - Metin/yazı içerme
   - Logo gösterme
   - İnsan yüzü close-up
   - Çok hızlı kamera hareketi

### ÖRNEK İYİ PROMPTLAR:

Tarım:
"Slow cinematic tracking shot through a modern greenhouse, rows of healthy green plants with small IoT sensors attached to soil, morning sunlight streaming through glass panels creating soft shadows, water droplets on leaves glistening, color palette of olive green and soft earth tones, peaceful and technological atmosphere"

Enerji:
"Smooth dolly shot revealing a wall of digital energy meters with blue LED displays showing real-time data, soft industrial lighting, data visualization particles flowing between meters, olive green and sky blue accent colors, professional corporate environment"

### ŞİMDİ PROMPT YAZ:

Yukarıdaki kurallara uyarak, verilen post için TEK bir İngilizce video prompt yaz.
Sadece prompt'u yaz, başka açıklama yapma. Tırnak işareti kullanma.
"""

    logger.info(f"Generating video prompt for topic: {topic}")
    result = await run_claude_code(prompt, timeout=90)

    # Temizle
    result = result.strip()

    # Tırnak işaretlerini kaldır
    if result.startswith('"') and result.endswith('"'):
        result = result[1:-1]
    if result.startswith("'") and result.endswith("'"):
        result = result[1:-1]

    logger.info(f"Video prompt generated: {result[:100]}...")
    return result


async def generate_flux_prompt(post_text: str, topic: str) -> str:
    """
    Claude Code ile FLUX.2 Pro için optimize edilmiş prompt üret.

    Args:
        post_text: Türkçe post metni
        topic: Konu

    Returns:
        İngilizce FLUX prompt
    """
    short_post = post_text[:400] if len(post_text) > 400 else post_text

    prompt = f"""
/opt/olivenet-social-bot/context/flux-prompting-guide.md dosyasını oku.
/opt/olivenet-social-bot/context/company-profile.md dosyasını oku.

## GÖREV: FLUX.2 Pro için Profesyonel Görsel Prompt'u

Post metni (Türkçe): {short_post}
Konu: {topic}

### FLUX PROMPT KURALLARI:

1. **DİL**: Mutlaka İNGİLİZCE yaz

2. **FRAMEWORK**: Subject + Action + Style + Context
   - En önemli elementler BAŞTA
   - 40-80 kelime arası ideal

3. **OLIVENET MARKA KİMLİĞİ**:
   - Renkler: olive green (#4a7c4a), sky blue (#38bdf8)
   - Profesyonel, modern, teknolojik
   - Temiz, minimal estetik

4. **KONUYA GÖRE GÖRSEL TEMALAR**:

   AKILLI TARIM / SERA:
   - Modern sera, yeşil bitkiler, IoT sensörler
   - Doğal güneş ışığı, soft shadows
   - Toprak nem sensörleri, damla sulama
   - "commercial agriculture photography style"

   ENERJİ İZLEME:
   - Dijital enerji sayaçları, LED göstergeler
   - Endüstriyel tesis ortamı
   - Data visualization, dashboard ekranları
   - "professional industrial photography"

   KESTİRİMCİ BAKIM:
   - CNC makineler, endüstriyel ekipman
   - Vibrasyon sensörleri, diagnostik ekranlar
   - Mühendis tablet ile çalışıyor
   - "corporate industrial photography style"

   BİNA OTOMASYONU:
   - Modern ofis, akıllı termostat
   - Cam, çelik, minimal mimari
   - Konfor ve teknoloji birleşimi
   - "architectural interior photography"

5. **TEKNİK DETAYLAR**:
   - 1024x1024 kare format için kompozisyon
   - Shallow depth of field (f/2.8)
   - Soft, professional lighting
   - Clean background

6. **ÖRNEK PROMPT YAPISI**:
   "[Ana konu detaylı], [aksiyon/durum], [ortam], [ışık], olive green (#4a7c4a) and sky blue (#38bdf8) accent colors, [stil], [teknik], [atmosfer]"

7. **YASAKLAR**:
   - Negatif prompt KULLANMA
   - "Olivenet" yazısı EKLEME (sonra ekleriz)
   - Çok karmaşık sahne YAPMA

### ŞİMDİ PROMPT YAZ:

Yukarıdaki kurallara uyarak, verilen post için TEK bir İngilizce görsel prompt yaz.
Sadece prompt'u yaz, başka açıklama yapma.
"""

    logger.info(f"Generating FLUX prompt for topic: {topic}")
    result = await run_claude_code(prompt, timeout=90)

    # Temizle
    result = result.strip()
    if result.startswith('"') and result.endswith('"'):
        result = result[1:-1]
    if result.startswith("'") and result.endswith("'"):
        result = result[1:-1]

    logger.info(f"FLUX prompt generated: {result[:100]}...")
    return result


async def generate_carousel_slide_html(
    slide_data: Dict,
    slide_number: int,
    total_slides: int,
    topic: str
) -> str:
    """
    Carousel slide için HTML oluştur.

    Args:
        slide_data: {"title": "...", "content": "...", "slide_type": "cover/content/stats/cta"}
        slide_number: 1, 2, 3... (1-indexed)
        total_slides: Toplam slide sayısı
        topic: Ana konu

    Returns:
        Complete HTML code for the slide (1080x1080px)
    """
    slide_type = slide_data.get("slide_type", "content")
    title = slide_data.get("title", "")
    content = slide_data.get("content", "")

    # Logo base64 verisini oku
    try:
        from app.logo_data import LOGO_BASE64
        logo_img = LOGO_BASE64.strip()
    except Exception:
        logo_img = ""

    prompt = f"""
Instagram carousel için profesyonel bir HTML slide tasarla.

## SLIDE BİLGİSİ:
- Slide {slide_number}/{total_slides}
- Tip: {slide_type}
- Başlık: {title}
- İçerik: {content}
- Ana Konu: {topic}

## TASARIM SİSTEMİ (Website ile Tutarlı):

### RENK PALETİ:
- olive-900: #1a2e1a (en koyu, stats arka plan)
- olive-800: #243524
- olive-700: #2d4a2d (primary gradient başlangıç)
- olive-600: #3a5f3a
- olive-500: #4a7c4a (ana vurgu, ikon)
- olive-400: #5e9a5e
- olive-300: #7ab87a
- olive-200: #a3d4a3 (label metni)
- olive-100: #d1e8d1
- olive-50:  #e8f4e8 (en açık, highlight)
- Arka plan koyu: #0a0a0a
- sky-400: #38bdf8 (accent)
- Beyaz: #fafafa, Muted: #a3a3a3

### TİPOGRAFİ (MOBİL ODAKLI - 1080x1080px):
⚠️ Instagram'da insanlar 3 saniyede karar veriyor. BÜYÜK, NET yazılar şart!

- Font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif
- H1 (Ana başlık): 72-96px, font-weight: 700-800
- H2 (Alt başlık): 48-64px, font-weight: 700
- H3: 36-40px, font-weight: 600
- Liste maddeleri: 36-48px, font-weight: 500
- Body/Açıklama: 32-36px, font-weight: 400
- Small (en küçük): 24px minimum

İÇERİK LİMİTLERİ (ZORUNLU):
- Başlık: Max 40 karakter
- Her bullet: Max 6-8 kelime
- Slide başına: Max 3-4 ana nokta
- PARAGRAF YASAK - sadece kısa maddeler
- Bol whitespace kullan

### BORDER RADIUS & SPACING:
- Card: 16px (rounded-2xl)
- CTA Banner: 24px (rounded-3xl)
- Icon container: 12px
- Button: 8px
- Padding: 48px container

## SLIDE TİPLERİNE GÖRE WEBSİTE STİLLERİ:

**cover** (Hero Section Stili):
- Arka plan: linear-gradient(to bottom right, #2d4a2d, #1a2e1a)
- Grid pattern overlay: linear-gradient(to right, rgba(74,124,74,0.1) 1px, transparent 1px), linear-gradient(to bottom, rgba(74,124,74,0.1) 1px, transparent 1px); background-size: 40px 40px
- Büyük başlık: 80-96px, font-weight: 800, #fafafa (MOBİL İÇİN BÜYÜK!)
- Alt başlık: 40px, #d1e8d1 (olive-100)
- Dekoratif blur orb: 200px, rgba(94,154,94,0.2), blur(60px)
- Minimal, temiz görünüm
- MAX 40 karakter başlık

**content** (Feature Card Stili):
- Arka plan: #0a0a0a veya gradient
- Her madde bir kart: background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px
- Hover efekti: border-color: rgba(74,124,74,0.3)
- İkon container: 48x48px, background: rgba(74,124,74,0.1), border-radius: 12px
- İkon rengi: #4a7c4a
- Title: 48px, font-weight: 700, #fafafa (MOBİL İÇİN BÜYÜK!)
- Description/Bullets: 32-36px, #a3a3a3
- MAX 3 bullet point per slide
- Her bullet MAX 6-8 kelime

**stats** (Stats Section Stili):
- Arka plan: #1a2e1a (olive-900)
- Büyük rakam: 96-120px, font-weight: 700, #ffffff (DEV RAKAMLAR!)
- Suffix (%, +): aynı boyut, #4a7c4a (olive-500)
- Label: 24px, #a3d4a3 (olive-200)
- Grid layout: 2x2 veya tek büyük stat
- Alt border: 1px solid rgba(255,255,255,0.1)
- MAX 3 stat per slide

**comparison** (Feature Card Varyasyonu):
- Yan yana iki kolon
- Sol kolon: ✗ ikonlu, rgba(239,68,68,0.1) arka plan
- Sağ kolon: ✓ ikonlu, rgba(74,124,74,0.1) arka plan
- Border-radius: 16px
- Başlık: 48px, liste: 36px

**cta** (CTA Banner Stili):
- Arka plan: linear-gradient(to bottom right, #3a5f3a, #1a2e1a)
- Grid pattern: rgba(255,255,255,0.03)
- Glow orb: sağ üst, rgba(94,154,94,0.2), blur(60px)
- Başlık: 64-72px, font-weight: 800, #ffffff (BÜYÜK CTA!)
- "Kaydet! 🔖" ve "Takip Et!" CTA butonları (48px buton text)
- Buton: background: #ffffff, color: #1a2e1a, border-radius: 8px, padding: 16px 32px
- @olivenet.io: 32px, #d1e8d1
- Logo sol alt köşe

## TASARIM KURALLARI (ZORUNLU):

1. **BOYUT**: 1080x1080px (Instagram kare)

2. **EFEKTLER**:
   - Glass: background: rgba(255,255,255,0.05); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1);
   - Grid pattern: background-image ile 40px grid
   - Glow orbs: büyük blur'lu dekoratif elementler

3. **LAYOUT**:
   - Padding: min 48px her yönde
   - Slide numarası: Sağ üst köşe ({slide_number}/{total_slides}), 18px, #a3a3a3
   - Son slide'da sol alt köşeye logo ekle

4. **LOGO** (sadece son slide için):
   ```html
   <div style="position:absolute;bottom:32px;left:32px;display:flex;align-items:center;gap:12px;">
     <img src="{{{{logo}}}}" style="width:48px;height:48px;border-radius:8px;">
     <span style="color:#ffffff;font-size:22px;font-weight:600;">Olivenet</span>
   </div>
   ```

## CRITICAL SPELLING RULES:
- "Olivenet" - NOT "Ovenet", "Oivenet", "Olivnet", "Oliveneet"
- "olivenet.io" - NOT "olivarbus", "olivarplus", "olivaborus", "olivaborpus" (küçük harf!)
- "LoRaWAN" - NOT "Lorawan", "LoraWAN", "Lorwan", "Lowaran"
- "IoT" - NOT "Iot", "IOT", "lot", "iiot"
- "KKTC" - NOT "Kktc", "kktc"
- "SCADA" - NOT "Scada", "scada"
- "MQTT" - NOT "Mqtt", "mqtt"

⚠️ MARKA YAZIMI KRİTİK! Double-check ALL brand names before output!

## ÇIKTI:
- Sadece tam HTML kodu döndür
- <!DOCTYPE html> ile başla
- Markdown code block (```) KULLANMA
- Açıklama yazma
- Tüm CSS inline olmalı
- HTML içinde {{{{logo}}}} placeholder kullan (sadece son slide)
"""

    logger.info(f"Generating carousel slide HTML: {slide_number}/{total_slides} ({slide_type})")
    result = await run_claude_code(prompt, timeout=settings.claude_timeout_visual)

    # Clean up and extract HTML
    result = extract_html(result)

    # Logo placeholder'ı gerçek base64 ile değiştir (son slide için)
    if logo_img and "{{logo}}" in result:
        result = result.replace("{{logo}}", logo_img)

    return result


# =============================================================================
# YENİ TEMPLATE GENERATOR FONKSİYONLARI
# =============================================================================

async def generate_dashboard_data(post_text: str, topic: str) -> dict:
    """
    Dashboard style infografik için JSON veri üret.

    Args:
        post_text: Post metni
        topic: Konu

    Returns:
        dict: Dashboard template için veri
    """
    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için DASHBOARD style infografik verisi üret.

KURALLAR:
- title: Dashboard başlığı, max 30 karakter
- metrics: 2 metrik (icon, value, label)
  * icon: thermometer, droplet, sun, wind, gauge, bolt
  * value: Kısa değer (örn: "22°C", "54%", "8 kWh")
  * label: Metrik etiketi (örn: "Sıcaklık", "Nem")
- progress: Yüzde değeri ve etiketi
  * value: 0-100 arası sayı
  * label: Progress etiketi (örn: "Su Tasarrufu")
- status: 2 status badge
  * label: Status etiketi (örn: "Pompa", "Vana")
  * active: true veya false
- variant: tarim, enerji, bina veya boş

SADECE geçerli JSON döndür:
{{"title": "...", "metrics": [{{"icon": "...", "value": "...", "label": "..."}}, {{"icon": "...", "value": "...", "label": "..."}}], "progress": {{"value": 65, "label": "..."}}, "status": [{{"label": "...", "active": true}}, {{"label": "...", "active": true}}], "variant": "..."}}
"""

    logger.info(f"Generating dashboard data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)

        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)

        data = json.loads(result)
        return data

    except Exception as e:
        logger.error(f"Dashboard data generation error: {e}")
        return {
            "title": "Sistem Durumu",
            "metrics": [
                {"icon": "thermometer", "value": "22°C", "label": "Sıcaklık"},
                {"icon": "droplet", "value": "54%", "label": "Nem"}
            ],
            "progress": {"value": 65, "label": "Verimlilik"},
            "status": [
                {"label": "Sistem", "active": True},
                {"label": "Bağlantı", "active": True}
            ],
            "variant": ""
        }


async def generate_dashboard_html(post_text: str, topic: str) -> str:
    """
    Dashboard style infografik HTML üret.
    """
    import os

    data = await generate_dashboard_data(post_text, topic)

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "dashboard-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logo_data = ""

    # Placeholder'ları değiştir
    html = html.replace("{{TITLE}}", data.get("title", "Dashboard"))
    html = html.replace("{{VARIANT}}", data.get("variant", ""))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    # Metrikler
    metrics = data.get("metrics", [])
    if len(metrics) >= 1:
        html = html.replace("{{METRIC_1_ICON}}", get_icon_svg(metrics[0].get("icon", "cpu")))
        html = html.replace("{{METRIC_1_VALUE}}", metrics[0].get("value", "N/A"))
        html = html.replace("{{METRIC_1_LABEL}}", metrics[0].get("label", "Metrik 1"))
    if len(metrics) >= 2:
        html = html.replace("{{METRIC_2_ICON}}", get_icon_svg(metrics[1].get("icon", "cpu")))
        html = html.replace("{{METRIC_2_VALUE}}", metrics[1].get("value", "N/A"))
        html = html.replace("{{METRIC_2_LABEL}}", metrics[1].get("label", "Metrik 2"))

    # Progress
    progress = data.get("progress", {})
    html = html.replace("{{PROGRESS_VALUE}}", str(progress.get("value", 50)))
    html = html.replace("{{PROGRESS_LABEL}}", progress.get("label", "İlerleme"))

    # Status
    status_list = data.get("status", [])
    if len(status_list) >= 1:
        html = html.replace("{{STATUS_1_LABEL}}", status_list[0].get("label", "Status 1"))
        html = html.replace("{{STATUS_1_ACTIVE}}", "active" if status_list[0].get("active") else "")
    if len(status_list) >= 2:
        html = html.replace("{{STATUS_2_LABEL}}", status_list[1].get("label", "Status 2"))
        html = html.replace("{{STATUS_2_ACTIVE}}", "active" if status_list[1].get("active") else "")

    logger.info(f"Dashboard infographic generated: {data.get('title')}")
    return html


async def generate_comparison_data(post_text: str, topic: str) -> dict:
    """
    Comparison style infografik için JSON veri üret.
    """
    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için COMPARISON style infografik verisi üret.
3 seçenek karşılaştırması yap.

KURALLAR:
- title: Karşılaştırma başlığı, max 40 karakter
- spec_labels: 3 özellik etiketi (örn: "Menzil", "Pil Ömrü", "Maliyet")
- options: 3 seçenek
  * name: Seçenek adı (örn: "WiFi", "LoRaWAN", "4G/LTE")
  * icon: wifi, radio, signal, bluetooth, satellite, network
  * recommended: true/false (sadece 1 tanesi true)
  * specs: 3 özellik değeri

SADECE geçerli JSON döndür:
{{"title": "...", "spec_labels": ["...", "...", "..."], "options": [{{"name": "...", "icon": "...", "recommended": false, "specs": ["...", "...", "..."]}}, {{"name": "...", "icon": "...", "recommended": true, "specs": ["...", "...", "..."]}}, {{"name": "...", "icon": "...", "recommended": false, "specs": ["...", "...", "..."]}}]}}
"""

    logger.info(f"Generating comparison data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)

        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)

        data = json.loads(result)
        return data

    except Exception as e:
        logger.error(f"Comparison data generation error: {e}")
        return {
            "title": "Hangi Teknolojiyi Seçmeli?",
            "spec_labels": ["Menzil", "Pil Ömrü", "Maliyet"],
            "options": [
                {"name": "WiFi", "icon": "wifi", "recommended": False, "specs": ["100m", "Kısa", "Düşük"]},
                {"name": "LoRaWAN", "icon": "radio", "recommended": True, "specs": ["15km", "5+ yıl", "Orta"]},
                {"name": "4G/LTE", "icon": "signal", "recommended": False, "specs": ["Sınırsız", "Orta", "Yüksek"]}
            ]
        }


async def generate_comparison_html(post_text: str, topic: str) -> str:
    """
    Comparison style infografik HTML üret.
    """
    import os

    data = await generate_comparison_data(post_text, topic)

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "comparison-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logo_data = ""

    # Placeholder'ları değiştir
    html = html.replace("{{TITLE}}", data.get("title", "Karşılaştırma"))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    # Spec labels
    spec_labels = data.get("spec_labels", ["Özellik 1", "Özellik 2", "Özellik 3"])
    html = html.replace("{{SPEC_1_LABEL}}", spec_labels[0] if len(spec_labels) > 0 else "Özellik 1")
    html = html.replace("{{SPEC_2_LABEL}}", spec_labels[1] if len(spec_labels) > 1 else "Özellik 2")
    html = html.replace("{{SPEC_3_LABEL}}", spec_labels[2] if len(spec_labels) > 2 else "Özellik 3")

    # Options
    options = data.get("options", [])
    for i, opt in enumerate(options[:3], 1):
        html = html.replace(f"{{{{OPTION_{i}_NAME}}}}", opt.get("name", f"Seçenek {i}"))
        html = html.replace(f"{{{{OPTION_{i}_ICON}}}}", get_icon_svg(opt.get("icon", "cpu")))

        if opt.get("recommended"):
            html = html.replace(f"{{{{OPTION_{i}_RECOMMENDED}}}}", "recommended")
            html = html.replace(f"{{{{OPTION_{i}_BADGE}}}}", '<div class="recommended-badge">Önerilen</div>')
        else:
            html = html.replace(f"{{{{OPTION_{i}_RECOMMENDED}}}}", "")
            html = html.replace(f"{{{{OPTION_{i}_BADGE}}}}", "")

        specs = opt.get("specs", ["N/A", "N/A", "N/A"])
        html = html.replace(f"{{{{OPTION_{i}_SPEC_1}}}}", specs[0] if len(specs) > 0 else "N/A")
        html = html.replace(f"{{{{OPTION_{i}_SPEC_2}}}}", specs[1] if len(specs) > 1 else "N/A")
        html = html.replace(f"{{{{OPTION_{i}_SPEC_3}}}}", specs[2] if len(specs) > 2 else "N/A")

    logger.info(f"Comparison infographic generated: {data.get('title')}")
    return html


async def generate_process_data(post_text: str, topic: str) -> dict:
    """
    Process style infografik için JSON veri üret.
    """
    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için PROCESS style infografik verisi üret.
3 adımlı bir süreç oluştur.

KURALLAR:
- title: Süreç başlığı, max 35 karakter
- steps: 3 adım
  * icon: radio, settings, chart, download, link, check, play, shield
  * title: Adım başlığı, max 15 karakter
  * subtitle: Adım açıklaması, max 25 karakter
- variant: tarim, enerji, bina, bakim veya boş

SADECE geçerli JSON döndür:
{{"title": "...", "steps": [{{"icon": "...", "title": "...", "subtitle": "..."}}, {{"icon": "...", "title": "...", "subtitle": "..."}}, {{"icon": "...", "title": "...", "subtitle": "..."}}], "variant": "..."}}
"""

    logger.info(f"Generating process data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)

        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)

        data = json.loads(result)
        return data

    except Exception as e:
        logger.error(f"Process data generation error: {e}")
        return {
            "title": "IoT Kurulum Adımları",
            "steps": [
                {"icon": "radio", "title": "Kur", "subtitle": "Sensör yerleştir"},
                {"icon": "settings", "title": "Bağla", "subtitle": "Gateway bağlan"},
                {"icon": "chart", "title": "İzle", "subtitle": "Dashboard izle"}
            ],
            "variant": ""
        }


async def generate_process_html(post_text: str, topic: str) -> str:
    """
    Process style infografik HTML üret.
    """
    import os

    data = await generate_process_data(post_text, topic)

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "process-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logo_data = ""

    # Placeholder'ları değiştir
    html = html.replace("{{TITLE}}", data.get("title", "Süreç"))
    html = html.replace("{{VARIANT}}", data.get("variant", ""))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    # Steps
    steps = data.get("steps", [])
    for i, step in enumerate(steps[:3], 1):
        html = html.replace(f"{{{{STEP_{i}_ICON}}}}", get_icon_svg(step.get("icon", "check")))
        html = html.replace(f"{{{{STEP_{i}_TITLE}}}}", step.get("title", f"Adım {i}"))
        html = html.replace(f"{{{{STEP_{i}_SUBTITLE}}}}", step.get("subtitle", ""))

    logger.info(f"Process infographic generated: {data.get('title')}")
    return html


async def generate_quote_data(post_text: str, topic: str) -> dict:
    """
    Quote style infografik için JSON veri üret.
    """
    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için QUOTE style infografik verisi üret.
Dikkat çekici bir alıntı/mesaj oluştur.

KURALLAR:
- quote: Ana mesaj/alıntı, max 60 karakter, etkileyici ve kısa
- icon: Ana ikon (lightbulb, quote, star, info, target, rocket)
- category: Kategori etiketi (örn: "Sera Otomasyonu", "Enerji Tasarrufu")
- category_icon: Kategori ikonu (leaf, bolt, building, gear)
- variant: tarim, enerji, bina, bakim veya boş

SADECE geçerli JSON döndür:
{{"quote": "...", "icon": "...", "category": "...", "category_icon": "...", "variant": "..."}}
"""

    logger.info(f"Generating quote data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)

        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)

        data = json.loads(result)
        return data

    except Exception as e:
        logger.error(f"Quote data generation error: {e}")
        return {
            "quote": "Akıllı çözümlerle geleceğe hazır olun",
            "icon": "lightbulb",
            "category": "IoT Çözümleri",
            "category_icon": "cpu",
            "variant": ""
        }


async def generate_quote_html(post_text: str, topic: str) -> str:
    """
    Quote style infografik HTML üret.
    """
    import os

    data = await generate_quote_data(post_text, topic)

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "quote-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logo_data = ""

    # Placeholder'ları değiştir
    html = html.replace("{{QUOTE}}", data.get("quote", "Akıllı çözümler"))
    html = html.replace("{{ICON_SVG}}", get_icon_svg(data.get("icon", "lightbulb")))
    html = html.replace("{{CATEGORY}}", data.get("category", "IoT"))
    html = html.replace("{{CATEGORY_ICON_SVG}}", get_icon_svg(data.get("category_icon", "cpu")))
    html = html.replace("{{VARIANT}}", data.get("variant", ""))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    logger.info(f"Quote infographic generated: {data.get('quote')[:30]}...")
    return html


# =============================================================================
# TEMPLATE SEÇİM SİSTEMİ
# =============================================================================
TEMPLATE_KEYWORDS = {
    "before_after": ["önce", "sonra", "dönüşüm", "değişim", "eski", "yeni", "karşılaştır", "geçiş", "fark"],
    "checklist": ["liste", "yapılacak", "kontrol", "checklist", "step", "madde", "sıra", "todo"],
    "timeline": ["yıl", "tarih", "süreç", "aşama", "milestone", "2024", "2025", "yolculuk", "gelişim"],
    "feature_grid": ["özellik", "feature", "4 madde", "neler var", "içerir", "avantaj", "fayda"],
    "big_number": ["yüzde", "%", "milyon", "bin", "rakam", "istatistik", "oran", "tasarruf"],
    "billboard": ["tek", "vurgu", "highlight", "ana", "öne çıkan"],
    "dashboard": ["metrik", "dashboard", "panel", "gösterge", "sensör", "izleme"],
    "comparison": ["vs", "karşılaştır", "hangisi", "fark", "seçenek", "alternatif"],
    "process": ["nasıl", "süreç", "adım adım", "kurulum", "uygulama", "adımları", "adım", "rehber"],
    "quote": ["söz", "quote", "ilham", "mesaj", "motivasyon"]
}


def select_template(topic: str, post_text: str = "") -> str:
    """
    Konuya ve içeriğe göre en uygun template'i seç.

    Args:
        topic: Konu başlığı
        post_text: Post metni (opsiyonel)

    Returns:
        Template adı (billboard, dashboard, comparison, process, quote,
                      before_after, checklist, timeline, feature_grid, big_number)
    """
    text = f"{topic} {post_text}".lower()

    scores = {}
    for template, keywords in TEMPLATE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        scores[template] = score

    # En yüksek skorlu template
    best = max(scores, key=scores.get)

    # Fallback: eğer skor 0 ise billboard döndür
    result = best if scores[best] > 0 else "billboard"
    logger.info(f"Template selected: {result} (scores: {scores})")
    return result


# =============================================================================
# BEFORE/AFTER TEMPLATE
# =============================================================================
async def generate_before_after_data(post_text: str, topic: str) -> dict:
    """Before/After style infografik için JSON veri üret."""
    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için BEFORE/AFTER (ÖNCE/SONRA) karşılaştırması yap.

KURALLAR:
- title: Ana başlık, max 50 karakter
- before_title: "ÖNCE" veya benzer
- before_items: 3 sorun/eski durum (kısa maddeler)
- after_title: "SONRA" veya benzer
- after_items: 3 çözüm/yeni durum (kısa maddeler)
- arrow_text: Geçiş metni (örn: "DÖNÜŞÜM", "IoT İLE")
- variant: tarim, enerji, bakim, bina veya boş

SADECE geçerli JSON döndür:
{{"title": "...", "before_title": "ÖNCE", "before_items": ["...", "...", "..."], "after_title": "SONRA", "after_items": ["...", "...", "..."], "arrow_text": "DÖNÜŞÜM", "variant": ""}}
"""

    logger.info(f"Generating before/after data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)
        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)
        return json.loads(result)

    except Exception as e:
        logger.error(f"Before/after data generation error: {e}")
        return {
            "title": "Akıllı Dönüşüm",
            "before_title": "ÖNCE",
            "before_items": ["Manuel kontrol", "Yüksek maliyet", "Veri eksikliği"],
            "after_title": "SONRA",
            "after_items": ["Otomatik izleme", "Maliyet tasarrufu", "Gerçek zamanlı veri"],
            "arrow_text": "DÖNÜŞÜM",
            "variant": ""
        }


async def generate_before_after_html(post_text: str, topic: str) -> str:
    """Before/After style infografik HTML üret."""
    import os

    data = await generate_before_after_data(post_text, topic)

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "before-after-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logo_data = ""

    # Placeholder'ları değiştir
    html = html.replace("{{TITLE}}", data.get("title", "Dönüşüm"))
    html = html.replace("{{BEFORE_TITLE}}", data.get("before_title", "ÖNCE"))
    html = html.replace("{{AFTER_TITLE}}", data.get("after_title", "SONRA"))
    html = html.replace("{{ARROW_TEXT}}", data.get("arrow_text", "DÖNÜŞÜM"))
    html = html.replace("{{VARIANT}}", data.get("variant", ""))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    # Before items
    before_items = data.get("before_items", [])
    before_html = "\n".join([
        f'<div class="box-item"><span class="icon">❌</span><span>{item}</span></div>'
        for item in before_items[:3]
    ])
    html = html.replace("{{BEFORE_ITEMS}}", before_html)

    # After items
    after_items = data.get("after_items", [])
    after_html = "\n".join([
        f'<div class="box-item"><span class="icon">✅</span><span>{item}</span></div>'
        for item in after_items[:3]
    ])
    html = html.replace("{{AFTER_ITEMS}}", after_html)

    logger.info(f"Before/After infographic generated: {data.get('title')}")
    return html


# =============================================================================
# CHECKLIST TEMPLATE
# =============================================================================
async def generate_checklist_data(post_text: str, topic: str) -> dict:
    """Checklist style infografik için JSON veri üret."""
    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için CHECKLIST (yapılacaklar listesi) oluştur.

KURALLAR:
- title: Ana başlık, max 50 karakter
- subtitle: Alt açıklama, max 60 karakter
- items: 4-5 madde, her biri:
  * text: Madde metni
  * status: "done", "pending", veya "waiting"
- progress: Yüzde değeri (0-100)
- variant: tarim, enerji, bakim, bina veya boş

SADECE geçerli JSON döndür:
{{"title": "...", "subtitle": "...", "items": [{{"text": "...", "status": "done"}}, {{"text": "...", "status": "done"}}, {{"text": "...", "status": "pending"}}, {{"text": "...", "status": "waiting"}}], "progress": 75, "variant": ""}}
"""

    logger.info(f"Generating checklist data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)
        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)
        return json.loads(result)

    except Exception as e:
        logger.error(f"Checklist data generation error: {e}")
        return {
            "title": "IoT Kurulum Checklist",
            "subtitle": "Adım adım rehber",
            "items": [
                {"text": "Sensör kurulumu", "status": "done"},
                {"text": "Gateway bağlantısı", "status": "done"},
                {"text": "Platform entegrasyonu", "status": "pending"},
                {"text": "Test ve doğrulama", "status": "waiting"}
            ],
            "progress": 50,
            "variant": ""
        }


async def generate_checklist_html(post_text: str, topic: str) -> str:
    """Checklist style infografik HTML üret."""
    import os

    data = await generate_checklist_data(post_text, topic)

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "checklist-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logo_data = ""

    progress = data.get("progress", 50)
    html = html.replace("{{TITLE}}", data.get("title", "Checklist"))
    html = html.replace("{{SUBTITLE}}", data.get("subtitle", ""))
    html = html.replace("{{PROGRESS}}", f"%{progress} Tamamlandı")
    html = html.replace("{{PROGRESS_PERCENT}}", str(progress))
    html = html.replace("{{VARIANT}}", data.get("variant", ""))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    # Checklist items
    status_icons = {"done": "✅", "pending": "⏳", "waiting": "⬜"}
    items = data.get("items", [])
    items_html = "\n".join([
        f'<div class="checklist-item {item.get("status", "waiting")}"><div class="check-icon">{status_icons.get(item.get("status", "waiting"), "⬜")}</div><div class="item-text">{item.get("text", "")}</div></div>'
        for item in items[:5]
    ])
    html = html.replace("{{CHECKLIST_ITEMS}}", items_html)

    logger.info(f"Checklist infographic generated: {data.get('title')}")
    return html


# =============================================================================
# TIMELINE TEMPLATE
# =============================================================================
async def generate_timeline_data(post_text: str, topic: str) -> dict:
    """Timeline style infografik için JSON veri üret."""
    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için TIMELINE (zaman çizelgesi) oluştur.

KURALLAR:
- title: Ana başlık, max 50 karakter
- subtitle: Alt açıklama, max 60 karakter
- milestones: 4 adet milestone:
  * date: Tarih/yıl (örn: "2023", "Q1")
  * title: Kısa başlık
  * desc: 1 cümle açıklama
  * icon: Emoji (🚀, 📊, ⚡, 🎯, 🌱, 📈)
  * active: true/false (sadece 1 tanesi true - en önemli)
- variant: tarim, enerji, bakim, bina veya boş

SADECE geçerli JSON döndür:
{{"title": "...", "subtitle": "...", "milestones": [{{"date": "2022", "title": "...", "desc": "...", "icon": "🚀", "active": false}}, {{"date": "2023", "title": "...", "desc": "...", "icon": "📊", "active": true}}, {{"date": "2024", "title": "...", "desc": "...", "icon": "⚡", "active": false}}, {{"date": "2025", "title": "...", "desc": "...", "icon": "🎯", "active": false}}], "variant": ""}}
"""

    logger.info(f"Generating timeline data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)
        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)
        return json.loads(result)

    except Exception as e:
        logger.error(f"Timeline data generation error: {e}")
        return {
            "title": "Proje Yolculuğu",
            "subtitle": "Adım adım gelişim",
            "milestones": [
                {"date": "2022", "title": "Başlangıç", "desc": "Proje fikri", "icon": "🚀", "active": False},
                {"date": "2023", "title": "Pilot", "desc": "İlk uygulama", "icon": "📊", "active": True},
                {"date": "2024", "title": "Büyüme", "desc": "Ölçeklendirme", "icon": "⚡", "active": False},
                {"date": "2025", "title": "Hedef", "desc": "100+ müşteri", "icon": "🎯", "active": False}
            ],
            "variant": ""
        }


async def generate_timeline_html(post_text: str, topic: str) -> str:
    """Timeline style infografik HTML üret."""
    import os

    data = await generate_timeline_data(post_text, topic)

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "timeline-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logo_data = ""

    html = html.replace("{{TITLE}}", data.get("title", "Timeline"))
    html = html.replace("{{SUBTITLE}}", data.get("subtitle", ""))
    html = html.replace("{{VARIANT}}", data.get("variant", ""))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    # Milestones
    milestones = data.get("milestones", [])
    milestones_html = "\n".join([
        f'''<div class="milestone {'active' if m.get('active') else ''}">
          <div class="milestone-dot">{m.get("icon", "●")}</div>
          <div class="milestone-date">{m.get("date", "")}</div>
          <div class="milestone-title">{m.get("title", "")}</div>
          <div class="milestone-desc">{m.get("desc", "")}</div>
        </div>'''
        for m in milestones[:4]
    ])
    html = html.replace("{{MILESTONES}}", milestones_html)

    logger.info(f"Timeline infographic generated: {data.get('title')}")
    return html


# =============================================================================
# FEATURE GRID TEMPLATE
# =============================================================================
async def generate_feature_grid_data(post_text: str, topic: str) -> dict:
    """Feature Grid style infografik için JSON veri üret."""
    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için FEATURE GRID (özellik kutuları) oluştur.

KURALLAR:
- title: Ana başlık, max 50 karakter
- subtitle: Alt açıklama, max 60 karakter
- features: Tam 4 adet özellik:
  * icon: Emoji (🌡️, 💧, ⚡, 📊, 🔒, 📡, 🌱, ⚙️)
  * title: Özellik adı, max 20 karakter
  * desc: 1 cümle açıklama, max 50 karakter
- variant: tarim, enerji, bakim, bina veya boş

SADECE geçerli JSON döndür:
{{"title": "...", "subtitle": "...", "features": [{{"icon": "🌡️", "title": "...", "desc": "..."}}, {{"icon": "💧", "title": "...", "desc": "..."}}, {{"icon": "⚡", "title": "...", "desc": "..."}}, {{"icon": "📊", "title": "...", "desc": "..."}}], "variant": ""}}
"""

    logger.info(f"Generating feature grid data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)
        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)
        return json.loads(result)

    except Exception as e:
        logger.error(f"Feature grid data generation error: {e}")
        return {
            "title": "Akıllı Çözüm Özellikleri",
            "subtitle": "Neler sunuyoruz?",
            "features": [
                {"icon": "🌡️", "title": "Sıcaklık İzleme", "desc": "Gerçek zamanlı takip"},
                {"icon": "💧", "title": "Nem Kontrolü", "desc": "Otomatik ayarlama"},
                {"icon": "⚡", "title": "Enerji Analizi", "desc": "Tüketim optimizasyonu"},
                {"icon": "📊", "title": "Raporlama", "desc": "Detaylı analizler"}
            ],
            "variant": ""
        }


async def generate_feature_grid_html(post_text: str, topic: str) -> str:
    """Feature Grid style infografik HTML üret."""
    import os

    data = await generate_feature_grid_data(post_text, topic)

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "feature-grid-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logo_data = ""

    html = html.replace("{{TITLE}}", data.get("title", "Özellikler"))
    html = html.replace("{{SUBTITLE}}", data.get("subtitle", ""))
    html = html.replace("{{VARIANT}}", data.get("variant", ""))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    # Features
    features = data.get("features", [])
    features_html = "\n".join([
        f'''<div class="feature-card">
          <div class="feature-icon">{f.get("icon", "⚙️")}</div>
          <div class="feature-title">{f.get("title", "")}</div>
          <div class="feature-desc">{f.get("desc", "")}</div>
        </div>'''
        for f in features[:4]
    ])
    html = html.replace("{{FEATURES}}", features_html)

    logger.info(f"Feature Grid infographic generated: {data.get('title')}")
    return html


# =============================================================================
# BIG NUMBER TEMPLATE
# =============================================================================
async def generate_big_number_data(post_text: str, topic: str) -> dict:
    """Big Number style infografik için JSON veri üret."""
    short_post = post_text[:300] if len(post_text) > 300 else post_text

    prompt = f"""
Post metni: {short_post}
Konu: {topic}

Bu içerik için BIG NUMBER (dev rakam vurgusu) oluştur.

KURALLAR:
- icon: Tek emoji (⚡, 🌱, 📊, 💧, 🔋, 📈)
- big_number: Etkileyici rakam (örn: "%40", "3x", "10K", "2.5M")
- label: Rakam etiketi, BÜYÜK HARF, max 25 karakter
- context: Açıklama cümlesi, max 80 karakter
- variant: tarim, enerji, bakim, bina veya boş

SADECE geçerli JSON döndür:
{{"icon": "⚡", "big_number": "%40", "label": "ENERJİ TASARRUFU", "context": "Akıllı izleme ile maliyetleri düşürün", "variant": "enerji"}}
"""

    logger.info(f"Generating big number data for topic: {topic}")

    try:
        result = await run_claude_code(prompt, timeout=45)
        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```json?\s*', '', result)
            result = re.sub(r'\s*```$', '', result)
        return json.loads(result)

    except Exception as e:
        logger.error(f"Big number data generation error: {e}")
        return {
            "icon": "📊",
            "big_number": "%30",
            "label": "VERİMLİLİK ARTIŞI",
            "context": "IoT çözümleriyle işletmenizi optimize edin",
            "variant": ""
        }


async def generate_big_number_html(post_text: str, topic: str) -> str:
    """Big Number style infografik HTML üret."""
    import os

    data = await generate_big_number_data(post_text, topic)

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "big-number-infographic.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        from app.logo_data import LOGO_BASE64
        logo_data = LOGO_BASE64.strip()
    except ImportError:
        logo_data = ""

    html = html.replace("{{ICON}}", data.get("icon", "📊"))
    html = html.replace("{{BIG_NUMBER}}", data.get("big_number", "%30"))
    html = html.replace("{{LABEL}}", data.get("label", "İSTATİSTİK"))
    html = html.replace("{{CONTEXT}}", data.get("context", ""))
    html = html.replace("{{VARIANT}}", data.get("variant", ""))
    html = html.replace("{{LOGO_DATA}}", logo_data)

    logger.info(f"Big Number infographic generated: {data.get('big_number')}")
    return html


# =============================================================================
# TEMPLATE FACTORY - Tüm template'leri tek fonksiyondan üret
# =============================================================================
async def generate_infographic_by_type(template_type: str, post_text: str, topic: str) -> str:
    """
    Belirtilen template tipine göre infografik HTML üret.

    Args:
        template_type: Template adı (billboard, dashboard, comparison, process, quote,
                       before_after, checklist, timeline, feature_grid, big_number)
        post_text: Post metni
        topic: Konu

    Returns:
        HTML string
    """
    generators = {
        "billboard": generate_billboard_html,
        "dashboard": generate_dashboard_html,
        "comparison": generate_comparison_html,
        "process": generate_process_html,
        "quote": generate_quote_html,
        "before_after": generate_before_after_html,
        "checklist": generate_checklist_html,
        "timeline": generate_timeline_html,
        "feature_grid": generate_feature_grid_html,
        "big_number": generate_big_number_html,
    }

    generator = generators.get(template_type, generate_billboard_html)
    logger.info(f"Generating infographic with template: {template_type}")
    return await generator(post_text, topic)


async def generate_auto_infographic(post_text: str, topic: str) -> str:
    """
    Konuya göre otomatik template seçerek infografik üret.

    Args:
        post_text: Post metni
        topic: Konu

    Returns:
        HTML string
    """
    template_type = select_template(topic, post_text)
    return await generate_infographic_by_type(template_type, post_text, topic)
