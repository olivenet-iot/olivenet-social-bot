"""
Video Visual Styles - Görsel stil tanımlamaları

Tüm video tipleri için kullanılabilir görsel stiller.
Her stil, video prompt'larına eklenecek prefix içerir.
"""

from typing import Dict, List

STYLE_CATEGORIES: Dict[str, dict] = {
    "realistic": {
        "name": "📽️ Gerçekçi",
        "styles": ["cinematic_4k", "3d_render", "neon_cyberpunk"]
    },
    "animation": {
        "name": "🎨 Animasyon",
        "styles": ["anime", "cartoon_3d", "claymation"]
    },
    "artistic": {
        "name": "🖌️ Sanatsal",
        "styles": ["watercolor", "pixel_art", "comic_book", "minimalist"]
    }
}

VIDEO_STYLES: Dict[str, dict] = {
    "cinematic_4k": {
        "name": "Sinematik 4K",
        "emoji": "🎬",
        "category": "realistic",
        "prefix": "4K cinematic, photorealistic, professional studio lighting, shallow depth of field, film color grading, ",
        "description": "Gerçekçi film kalitesi"
    },
    "anime": {
        "name": "Anime",
        "emoji": "🎌",
        "category": "animation",
        "prefix": "Anime style, Japanese animation, cel-shaded, vibrant colors, expressive characters, Studio Ghibli inspired, ",
        "description": "Japon animasyon tarzı"
    },
    "cartoon_3d": {
        "name": "3D Cartoon",
        "emoji": "🎨",
        "category": "animation",
        "prefix": "Pixar style 3D animation, stylized characters, vibrant saturated colors, soft global illumination, ",
        "description": "Pixar/Disney 3D tarzı"
    },
    "watercolor": {
        "name": "Suluboya",
        "emoji": "🖌️",
        "category": "artistic",
        "prefix": "Watercolor painting style, soft bleeding edges, flowing organic colors, artistic brush texture, dreamy atmosphere, ",
        "description": "Suluboya sanat tarzı"
    },
    "3d_render": {
        "name": "3D Render",
        "emoji": "💎",
        "category": "realistic",
        "prefix": "Photorealistic 3D render, Octane render quality, ray traced reflections, volumetric lighting, ",
        "description": "Fotorealistik 3D"
    },
    "pixel_art": {
        "name": "Pixel Art",
        "emoji": "👾",
        "category": "artistic",
        "prefix": "Pixel art style, 16-bit retro aesthetic, limited color palette, crisp pixelated edges, nostalgic gaming vibe, ",
        "description": "Retro piksel tarzı"
    },
    "comic_book": {
        "name": "Çizgi Roman",
        "emoji": "💥",
        "category": "artistic",
        "prefix": "Comic book style, bold black outlines, halftone dot shading, dynamic action poses, vibrant pop art colors, ",
        "description": "Çizgi roman tarzı"
    },
    "claymation": {
        "name": "Claymation",
        "emoji": "🧸",
        "category": "animation",
        "prefix": "Claymation stop-motion style, clay texture, handcrafted aesthetic, warm soft lighting, Wallace and Gromit inspired, ",
        "description": "Kil animasyon tarzı"
    },
    "minimalist": {
        "name": "Minimalist",
        "emoji": "⬜",
        "category": "artistic",
        "prefix": "Minimalist flat design, simple geometric shapes, clean lines, bold solid colors, ample negative space, ",
        "description": "Sade minimal tarz"
    },
    "neon_cyberpunk": {
        "name": "Neon Cyberpunk",
        "emoji": "🌃",
        "category": "realistic",
        "prefix": "Cyberpunk aesthetic, vivid neon lights, dark rainy atmosphere, holographic reflections, Blade Runner inspired, ",
        "description": "Neon siber atmosfer"
    }
}


def get_style_config(style_id: str) -> dict:
    """Stil konfigürasyonunu al."""
    return VIDEO_STYLES.get(style_id, VIDEO_STYLES["cinematic_4k"])


def get_style_prefix(style_id: str) -> str:
    """Stil için prompt prefix'i al."""
    return get_style_config(style_id).get("prefix", "")


def get_styles_by_category(category: str) -> List[str]:
    """Kategoriye göre stil listesi."""
    return STYLE_CATEGORIES.get(category, {}).get("styles", [])


def get_all_style_ids() -> List[str]:
    """Tüm stil ID'leri."""
    return list(VIDEO_STYLES.keys())


def get_style_display_name(style_id: str) -> str:
    """Stil görünen adını emoji ile al."""
    config = get_style_config(style_id)
    return f"{config['emoji']} {config['name']}"
