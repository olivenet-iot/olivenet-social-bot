"""
Video Visual Styles - Görsel stil tanımlamaları

Tüm video tipleri için kullanılabilir görsel stiller.
Her stil: prompt prefix + karakter tanımları + ses tipi içerir.
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

# Ses tipi tanımları
VOICE_TYPES = {
    "realistic": {
        "description": "Doğal, profesyonel sesler",
        "use_cartoon_voices": False
    },
    "cartoon": {
        "description": "Eğlenceli, karakteristik sesler",
        "use_cartoon_voices": True
    }
}

VIDEO_STYLES: Dict[str, dict] = {
    "cinematic_4k": {
        "name": "Sinematik 4K",
        "emoji": "🎬",
        "category": "realistic",
        "prefix": "4K cinematic, photorealistic, professional studio lighting, shallow depth of field, film color grading, ",
        "description": "Gerçekçi film kalitesi",
        "voice_type": "realistic",
        "character_male": (
            "Middle-aged man (45-55 years old), weathered sun-tanned face from outdoor work, "
            "simple work clothes (shirt, vest, cap), natural realistic appearance, "
            "speaking with concerned questioning tone, clear lip movements"
        ),
        "character_female": (
            "Professional woman (30-40 years old), confident posture, smart casual clothing, "
            "natural realistic appearance, speaking with reassuring knowledgeable tone, "
            "clear lip movements synchronized with speech"
        ),
        "scene_setting": "Outdoor setting in rural Turkey - farm, greenhouse, or agricultural field. Natural daylight, warm Mediterranean colors.",
        "tone_male": "with concerned, questioning tone",
        "tone_female": "with reassuring, confident tone"
    },
    "anime": {
        "name": "Anime",
        "emoji": "🎌",
        "category": "animation",
        "prefix": "Anime style, Japanese animation, cel-shaded, vibrant colors, expressive characters, Studio Ghibli inspired, ",
        "description": "Japon animasyon tarzı",
        "voice_type": "cartoon",
        "character_male": (
            "Anime-style male character, large expressive eyes, simplified facial features, "
            "colorful farmer outfit, exaggerated surprised expressions when asking questions, "
            "dynamic hand gestures, cel-shaded rendering"
        ),
        "character_female": (
            "Anime-style female character, big bright eyes, stylized professional look, "
            "confident anime pose, expressive face when explaining solutions, "
            "smooth cel-shaded animation style"
        ),
        "scene_setting": "Vibrant anime-style greenhouse or farm setting, saturated colors, stylized backgrounds with soft gradients, Studio Ghibli inspired atmosphere.",
        "tone_male": "with anime-style exaggerated surprised expressions",
        "tone_female": "with anime-style enthusiastic explaining gestures"
    },
    "cartoon_3d": {
        "name": "3D Cartoon",
        "emoji": "🎨",
        "category": "animation",
        "prefix": "Pixar style 3D animation, stylized characters, vibrant saturated colors, soft global illumination, ",
        "description": "Pixar/Disney 3D tarzı",
        "voice_type": "cartoon",
        "character_male": (
            "Pixar-style 3D animated farmer character, friendly exaggerated features, "
            "big expressive eyes, round approachable face, colorful overalls, "
            "comedic worried expressions, bouncy animated movements"
        ),
        "character_female": (
            "Pixar-style 3D animated tech consultant, warm friendly design, "
            "stylized proportions, confident cheerful expressions, "
            "smooth 3D animation, soft subsurface scattering on skin"
        ),
        "scene_setting": "Pixar-style colorful farm environment, soft lighting, vibrant saturated colors, whimsical atmosphere, rounded organic shapes.",
        "tone_male": "with Pixar-style comedic worried expressions",
        "tone_female": "with Pixar-style cheerful helpful demeanor"
    },
    "watercolor": {
        "name": "Suluboya",
        "emoji": "🖌️",
        "category": "artistic",
        "prefix": "Watercolor painting style, soft bleeding edges, flowing organic colors, artistic brush texture, dreamy atmosphere, ",
        "description": "Suluboya sanat tarzı",
        "voice_type": "realistic",
        "character_male": (
            "Watercolor-painted male figure, soft edges, artistic brush strokes, "
            "warm earth tones, gentle flowing movement, dreamy artistic style"
        ),
        "character_female": (
            "Watercolor-painted female figure, delicate brush strokes, "
            "soft pastel colors, elegant flowing appearance, artistic rendering"
        ),
        "scene_setting": "Dreamy watercolor landscape, soft bleeding colors, artistic brush texture, pastoral Turkish countryside with flowing organic shapes.",
        "tone_male": "with gentle worried expression",
        "tone_female": "with calm reassuring presence"
    },
    "3d_render": {
        "name": "3D Render",
        "emoji": "💎",
        "category": "realistic",
        "prefix": "Photorealistic 3D render, Octane render quality, ray traced reflections, volumetric lighting, ",
        "description": "Fotorealistik 3D",
        "voice_type": "realistic",
        "character_male": (
            "Photorealistic 3D rendered male, detailed skin textures, realistic clothing, "
            "professional 3D character model, natural expressions, "
            "ray-traced lighting on face"
        ),
        "character_female": (
            "Photorealistic 3D rendered female, detailed realistic features, "
            "professional appearance, subsurface scattering skin, "
            "volumetric lighting, cinema-quality 3D rendering"
        ),
        "scene_setting": "Photorealistic 3D rendered agricultural environment, volumetric god rays, ray-traced reflections, hyper-detailed textures.",
        "tone_male": "with realistic concerned expression",
        "tone_female": "with professional confident demeanor"
    },
    "pixel_art": {
        "name": "Pixel Art",
        "emoji": "👾",
        "category": "artistic",
        "prefix": "Pixel art style, 16-bit retro aesthetic, limited color palette, crisp pixelated edges, nostalgic gaming vibe, ",
        "description": "Retro piksel tarzı",
        "voice_type": "cartoon",
        "character_male": (
            "16-bit pixel art male character, limited color palette, "
            "retro game sprite style, simple expressive pixel face, "
            "nostalgic SNES-era aesthetic"
        ),
        "character_female": (
            "16-bit pixel art female character, crisp pixel edges, "
            "retro gaming aesthetic, charming simple design, "
            "expressive within pixel limitations"
        ),
        "scene_setting": "Retro 16-bit pixel art farm scene, limited color palette, crisp pixels, nostalgic video game backgrounds, SNES-era aesthetic.",
        "tone_male": "with retro game character worried pose",
        "tone_female": "with retro game character victory pose"
    },
    "comic_book": {
        "name": "Çizgi Roman",
        "emoji": "💥",
        "category": "artistic",
        "prefix": "Comic book style, bold black outlines, halftone dot shading, dynamic action poses, vibrant pop art colors, ",
        "description": "Çizgi roman tarzı",
        "voice_type": "cartoon",
        "character_male": (
            "Comic book style male character, bold black outlines, "
            "halftone shading, dynamic expressive poses, "
            "pop art colors, speech bubble ready expressions"
        ),
        "character_female": (
            "Comic book style female character, strong ink outlines, "
            "vibrant pop art coloring, confident superhero-like pose, "
            "dynamic comic panel aesthetic"
        ),
        "scene_setting": "Bold comic book panels, halftone dot backgrounds, vibrant pop art colors, dynamic action lines, speech bubble aesthetic.",
        "tone_male": "with dramatic comic-style worried expression",
        "tone_female": "with superhero-like confident stance"
    },
    "claymation": {
        "name": "Claymation",
        "emoji": "🧸",
        "category": "animation",
        "prefix": "Claymation stop-motion style, clay texture, handcrafted aesthetic, warm soft lighting, Wallace and Gromit inspired, ",
        "description": "Kil animasyon tarzı",
        "voice_type": "cartoon",
        "character_male": (
            "Claymation male character, visible clay texture, handmade aesthetic, "
            "charming imperfections, Wallace and Gromit inspired design, "
            "warm friendly appearance, stop-motion movement style"
        ),
        "character_female": (
            "Claymation female character, sculpted clay look, "
            "handcrafted charm, warm soft features, "
            "Aardman animation inspired, endearing stop-motion style"
        ),
        "scene_setting": "Handcrafted claymation set, miniature farm models, warm studio lighting, visible clay textures, charming stop-motion aesthetic.",
        "tone_male": "with charming stop-motion worried wiggle",
        "tone_female": "with endearing clay-animated helpful gestures"
    },
    "minimalist": {
        "name": "Minimalist",
        "emoji": "⬜",
        "category": "artistic",
        "prefix": "Minimalist flat design, simple geometric shapes, clean lines, bold solid colors, ample negative space, ",
        "description": "Sade minimal tarz",
        "voice_type": "realistic",
        "character_male": (
            "Minimalist flat design male figure, simple geometric shapes, "
            "clean lines, limited color palette, abstract representation, "
            "modern graphic design aesthetic"
        ),
        "character_female": (
            "Minimalist flat design female figure, geometric simplicity, "
            "bold solid colors, clean modern look, "
            "negative space utilization, abstract elegant design"
        ),
        "scene_setting": "Clean minimalist environment, flat design backgrounds, bold solid colors, ample negative space, modern graphic aesthetic.",
        "tone_male": "with subtle geometric expression shift",
        "tone_female": "with clean confident posture"
    },
    "neon_cyberpunk": {
        "name": "Neon Cyberpunk",
        "emoji": "🌃",
        "category": "realistic",
        "prefix": "Cyberpunk aesthetic, vivid neon lights, dark rainy atmosphere, holographic reflections, Blade Runner inspired, ",
        "description": "Neon siber atmosfer",
        "voice_type": "realistic",
        "character_male": (
            "Cyberpunk male character, neon-lit face, futuristic work gear, "
            "holographic interface reflections, rain-slicked appearance, "
            "Blade Runner inspired aesthetic"
        ),
        "character_female": (
            "Cyberpunk female tech expert, neon accent lighting, "
            "futuristic smart clothing, holographic displays, "
            "confident high-tech appearance, rain reflections"
        ),
        "scene_setting": "Futuristic cyberpunk greenhouse, neon lights, holographic displays, rain effects, dark moody atmosphere with vibrant accent colors.",
        "tone_male": "with noir-style troubled expression",
        "tone_female": "with tech-noir confident stance"
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


def get_character_descriptions(style_id: str) -> Dict[str, str]:
    """
    Stil için karakter tanımlarını al.

    Returns:
        {
            "male": "Karakter tanımı...",
            "female": "Karakter tanımı...",
            "scene": "Sahne tanımı...",
            "tone_male": "Erkek karakter tonu...",
            "tone_female": "Kadın karakter tonu..."
        }
    """
    config = get_style_config(style_id)
    return {
        "male": config.get("character_male", "Male character"),
        "female": config.get("character_female", "Female character"),
        "scene": config.get("scene_setting", "Professional setting"),
        "tone_male": config.get("tone_male", "with concerned, questioning tone"),
        "tone_female": config.get("tone_female", "with reassuring, confident tone")
    }


def get_voice_type(style_id: str) -> str:
    """
    Stil için ses tipini al.

    Returns:
        "realistic" veya "cartoon"
    """
    config = get_style_config(style_id)
    return config.get("voice_type", "realistic")


def should_use_cartoon_voices(style_id: str) -> bool:
    """
    Bu stil için cartoon sesler mi kullanılmalı?

    Returns:
        True: Cartoon/animation sesler kullan
        False: Realistic sesler kullan
    """
    voice_type = get_voice_type(style_id)
    return VOICE_TYPES.get(voice_type, {}).get("use_cartoon_voices", False)
