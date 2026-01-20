"""
Video Model Configurations
Multi-model voice reels support for Olivenet Social Bot

Models:
- sora-2: OpenAI Sora 2 (sora_helper.py)
- veo-2: Google Veo 2 (veo_helper.py)
- kling-2.1: Kuaishou Kling 2.1 (fal_helper.py)
- wan-2.1: Alibaba Wan 2.1 (fal_helper.py)
- minimax: Hailuo/Minimax (fal_helper.py)
"""

from typing import Dict, List, Optional

VIDEO_MODELS: Dict[str, dict] = {
    "sora-2": {
        "name": "Sora 2",
        "provider": "openai",
        "emoji": "🌟",
        "durations": [4, 8, 12],
        "default_duration": 12,
        "max_duration": 12,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_sora",
        "description": "En yüksek kalite, gerçekçi",
        "helper_module": "sora_helper",
        "helper_function": "generate_video_sora"
    },
    "sora-2-pro": {
        "name": "Sora 2 Pro",
        "provider": "openai",
        "emoji": "⭐",
        "durations": [10, 15, 25],
        "default_duration": 15,
        "max_duration": 25,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_sora",
        "description": "15-25s uzun video, native speech",
        "helper_module": "sora_helper",
        "helper_function": "generate_video_sora",
        "has_native_audio": True,
        "supports_speech": True,
        "conversational_only": True
    },
    "veo-2": {
        "name": "Veo 2",
        "provider": "google",
        "emoji": "🎥",
        "durations": [5, 8],
        "default_duration": 8,
        "max_duration": 8,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_veo",
        "description": "Hızlı ve tutarlı",
        "helper_module": "veo_helper",
        "helper_function": "generate_video_veo",
        "model_id": "veo-2"
    },
    "veo-3.1": {
        "name": "Veo 3.1",
        "provider": "google",
        "emoji": "🎬",
        "durations": [4, 6, 8],
        "default_duration": 8,
        "max_duration": 8,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_veo",
        "description": "Native audio + lip-sync (en iyi kalite)",
        "helper_module": "veo_helper",
        "helper_function": "generate_video_veo",
        "model_id": "veo-3.1-generate-preview",
        "has_native_audio": True,
        "supports_speech": True
    },
    "kling-2.5-pro": {
        "name": "Kling 2.5 Pro",
        "provider": "fal",
        "emoji": "🎬",
        "durations": [5, 10],
        "default_duration": 10,
        "max_duration": 10,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_kling",
        "description": "Hızlı üretim, hareketli sahneler",
        "helper_module": "fal_helper",
        "fal_model": "kling_pro",
        "has_native_audio": False,
        "disable_audio_for_voice": False
    },
    "kling-2.6-pro": {
        "name": "Kling 2.6 Pro",
        "provider": "fal",
        "emoji": "🎥",
        "durations": [5, 10],
        "default_duration": 10,
        "max_duration": 10,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_kling",
        "description": "Cinematic 1080p kalite ⭐",
        "helper_module": "fal_helper",
        "fal_model": "kling_26_pro",
        "has_native_audio": True,
        "disable_audio_for_voice": True  # TTS voiceover için native audio kapat
    },
    "wan-2.1": {
        "name": "Wan 2.1",
        "provider": "fal",
        "emoji": "🌊",
        "durations": [5, 10, 15],
        "default_duration": 15,
        "max_duration": 15,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_wan",
        "description": "15s uzun video!",
        "helper_module": "fal_helper",
        "fal_model": "wan_26"
    },
    "minimax": {
        "name": "Minimax",
        "provider": "fal",
        "emoji": "🎯",
        "durations": [5],
        "default_duration": 5,
        "max_duration": 5,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_hailuo",
        "description": "Hızlı ve ekonomik",
        "helper_module": "fal_helper",
        "fal_model": "hailuo_pro"
    }
}


def get_model_config(model_id: str) -> dict:
    """
    Get model configuration by ID.

    Args:
        model_id: Model identifier (e.g., "sora-2", "wan-2.1")

    Returns:
        Model configuration dict. Falls back to veo-2 if not found.
    """
    return VIDEO_MODELS.get(model_id, VIDEO_MODELS["veo-2"])


def get_available_models() -> List[str]:
    """
    Get list of available model IDs.

    Returns:
        List of model IDs
    """
    return list(VIDEO_MODELS.keys())


def get_model_durations(model_id: str) -> List[int]:
    """
    Get available durations for a model.

    Args:
        model_id: Model identifier

    Returns:
        List of supported durations in seconds
    """
    config = get_model_config(model_id)
    return config.get("durations", [8, 12])


def get_max_duration(model_id: str) -> int:
    """
    Get maximum supported duration for a model.

    Args:
        model_id: Model identifier (e.g., "veo-2", "kling-2.6-pro")

    Returns:
        Maximum duration in seconds (e.g., Veo=8, Kling=10, Sora=12, Wan=15)
    """
    config = get_model_config(model_id)
    return config.get("max_duration", 10)


def get_prompt_key(model_id: str) -> str:
    """
    Get the prompt key for selecting model-specific prompt from create_reels_prompt output.

    Args:
        model_id: Model identifier

    Returns:
        Prompt key (e.g., "video_prompt_sora", "video_prompt_wan")
    """
    config = get_model_config(model_id)
    return config.get("prompt_key", "video_prompt_veo")


def validate_duration(model_id: str, duration: int) -> int:
    """
    Validate and clamp duration to model's supported range.

    Args:
        model_id: Model identifier
        duration: Requested duration in seconds

    Returns:
        Valid duration (clamped to model's max if exceeded)
    """
    config = get_model_config(model_id)
    max_duration = config.get("max_duration", 12)
    durations = config.get("durations", [8, 12])

    # Clamp to max
    duration = min(duration, max_duration)

    # Find closest supported duration
    if duration not in durations:
        # Find the closest supported duration
        duration = min(durations, key=lambda x: abs(x - duration))

    return duration


def should_disable_audio(model_id: str, voice_mode: bool = False) -> bool:
    """
    Check if native audio should be disabled for this model.

    Args:
        model_id: Model identifier
        voice_mode: Whether TTS voiceover will be added

    Returns:
        True if native audio should be disabled
    """
    config = get_model_config(model_id)

    # If model has native audio and we're in voice mode, disable it
    if voice_mode and config.get("disable_audio_for_voice", False):
        return True

    return False
