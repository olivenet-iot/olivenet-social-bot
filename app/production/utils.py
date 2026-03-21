"""
Production Utilities - Pipeline'lar arası paylaşılan yardımcı fonksiyonlar
pipeline.py'dan extract edilmiştir.
"""

import subprocess
from enum import Enum


# ============ CONSTANTS ============

BROLL_AUDIO_DELAY = 1.5  # Silence at start of B-roll audio (seconds)
CONV_FREEZE_BUFFER = 0.3  # Buffer after last word for freeze frame


# ============ PIPELINE STATE ============

class PipelineState(Enum):
    """Pipeline durumları"""
    IDLE = "idle"
    PLANNING = "planning"
    AWAITING_TOPIC_APPROVAL = "awaiting_topic_approval"
    CREATING_CONTENT = "creating_content"
    AWAITING_CONTENT_APPROVAL = "awaiting_content_approval"
    CREATING_VISUAL = "creating_visual"
    AWAITING_VISUAL_APPROVAL = "awaiting_visual_approval"
    REVIEWING = "reviewing"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    ERROR = "error"


# ============ HELPER FUNCTIONS ============

def calculate_freeze_duration(video_duration: float, last_word_end: float) -> float:
    """
    Calculate freeze frame duration based on audio timing.
    Only returns > 0 if audio extends beyond video.
    """
    audio_end_with_buffer = last_word_end + CONV_FREEZE_BUFFER
    if audio_end_with_buffer > video_duration:
        return audio_end_with_buffer - video_duration
    return 0


async def add_freeze_frame(video_path: str, duration: float) -> str:
    """
    Add freeze frame to end of video using FFmpeg tpad filter.
    """
    output_path = video_path.replace(".mp4", "_freeze.mp4")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"tpad=stop_mode=clone:stop_duration={duration}",
        "-c:a", "copy",
        output_path
    ]

    print(f"[FREEZE FRAME] Adding {duration:.1f}s freeze to video...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Freeze frame failed: {result.stderr}")

    print(f"[FREEZE FRAME] Output: {output_path}")
    return output_path


def escape_md(value) -> str:
    """Telegram Markdown için güvenli escape - None ve boş değerleri de handle eder"""
    from telegram.helpers import escape_markdown
    if value is None:
        return "N/A"
    return escape_markdown(str(value))


def extract_shot_structure(speech_script: str, target_duration: int) -> list:
    """
    Speech script'ten shot yapısı çıkar.
    Her 4 saniye = 1 shot, video prompt ile senkronize edilecek.
    """
    if not speech_script:
        return []

    words = speech_script.split()
    num_shots = max(1, int(target_duration // 4))
    words_per_shot = max(1, len(words) // num_shots)

    shots = []
    for i in range(num_shots):
        start_time = i * 4
        end_time = min((i + 1) * 4, target_duration)

        start_idx = i * words_per_shot
        end_idx = min(start_idx + words_per_shot, len(words))
        shot_words = words[start_idx:end_idx]

        keywords = [w.strip('.,!?') for w in shot_words if len(w) > 4][:3]

        shots.append({
            "time": f"{start_time}-{end_time}s",
            "concept": " ".join(shot_words),
            "keywords": keywords
        })

    return shots
