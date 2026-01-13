"""
Audio utility functions for the Olivenet Social Bot.

This module provides audio manipulation helpers including:
- Adding silence/delay to audio files
- Audio duration utilities
"""

import os
import subprocess
from datetime import datetime
from typing import Optional


async def add_silence_prefix(
    audio_path: str,
    silence_duration: float = 1.5,
    output_dir: Optional[str] = None
) -> str:
    """
    Add silence to the beginning of an audio file.

    Args:
        audio_path: Path to the source audio file
        silence_duration: Duration of silence to add in seconds (default: 1.5)
        output_dir: Optional output directory (defaults to same as input)

    Returns:
        Path to the new audio file with silence prefix

    Raises:
        Exception: If FFmpeg fails to process the audio
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Determine output path
    if output_dir is None:
        output_dir = os.path.dirname(audio_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"delayed_{timestamp}.mp3")

    # FFmpeg command: generate silence + concatenate with original audio
    # anullsrc: generates silent audio
    # concat: joins silence and original audio
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={silence_duration}",
        "-i", audio_path,
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
        "-map", "[out]",
        "-c:a", "libmp3lame",
        "-q:a", "2",
        output_path
    ]

    print(f"[AUDIO] Adding {silence_duration}s silence prefix to audio...")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"FFmpeg silence prefix failed: {result.stderr}")

    print(f"[AUDIO] Delay added: {output_path}")
    return output_path


def get_audio_duration_sync(audio_path: str) -> float:
    """
    Get the duration of an audio file in seconds (synchronous).

    Args:
        audio_path: Path to the audio file

    Returns:
        Duration in seconds
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"FFprobe failed: {result.stderr}")

    return float(result.stdout.strip())
