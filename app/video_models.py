"""
Video Model Configurations
Multi-model voice reels support for Olivenet Social Bot

Models:
- sora-2: OpenAI Sora 2 (sora_helper.py)
- sora-2-pro: OpenAI Sora 2 Pro (sora_helper.py)
- kling-3.0-pro: Kuaishou Kling 3.0 Pro (kling_helper.py)
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
        "durations": [4, 8, 12],  # API limitation
        "default_duration": 12,
        "max_duration": 12,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_sora",
        "description": "Yüksek kalite, native speech (12s)",
        "helper_module": "sora_helper",
        "helper_function": "generate_video_sora",
        "has_native_audio": True,
        "supports_speech": True,
        "conversational_only": True
    },
    "kling-3.0-pro": {
        "name": "Kling 3.0 Pro",
        "provider": "kling",
        "emoji": "🔮",
        "durations": [5, 10, 15],
        "default_duration": 10,
        "max_duration": 15,
        "aspect_ratio": "9:16",
        "prompt_key": "video_prompt_kling3",
        "description": "Sinematik yönetmenlik, 15s, fizik tabanlı hareket ⭐",
        "helper_module": "kling_helper",
        "kling_model": "kling-v3",
        "has_native_audio": True,
        "disable_audio_for_voice": True
    },
}


def get_model_config(model_id: str) -> dict:
    """
    Get model configuration by ID.

    Args:
        model_id: Model identifier (e.g., "sora-2", "kling-3.0-pro")
                  Also accepts fal internal names (e.g., "kling_v3_pro")

    Returns:
        Model configuration dict. Falls back to kling-3.0-pro if not found.
    """
    # Direct key lookup
    if model_id in VIDEO_MODELS:
        return VIDEO_MODELS[model_id]

    # Reverse lookup by kling_model name (kling-v3 → kling-3.0-pro)
    for key, config in VIDEO_MODELS.items():
        if config.get("kling_model") == model_id:
            return config

    # Fallback
    return VIDEO_MODELS["kling-3.0-pro"]


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
        model_id: Model identifier (e.g., "kling-3.0-pro", "sora-2")

    Returns:
        Maximum duration in seconds (e.g., Kling=15, Sora=12)
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
    return config.get("prompt_key", "video_prompt_sora")


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
