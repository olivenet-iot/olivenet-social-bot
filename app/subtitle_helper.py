"""
Subtitle Helper - Whisper-based automatic subtitle generation

Uses OpenAI Whisper for word-level timestamp extraction and generates
ASS subtitle files for Instagram/TikTok style subtitles.
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

# Output directory
SUBTITLE_OUTPUT_DIR = Path("/opt/olivenet-social-bot/outputs/subtitles")

# Default subtitle style settings (Instagram/TikTok style)
DEFAULT_SUBTITLE_CONFIG = {
    "font_name": "DejaVu Sans",
    "font_size": 48,
    "primary_color": "&HFFFFFF",    # White (ASS uses AABBGGRR format)
    "outline_color": "&H000000",     # Black
    "outline_width": 3,
    "shadow": 0,
    "margin_v": 80,                  # Bottom margin for Instagram safe zone
    "alignment": 2,                  # Bottom center (1-3 bottom, 4-6 middle, 7-9 top)
    "bold": True,
    "max_chars_per_line": 35,
    "max_lines": 2,
    "min_duration": 1.0,             # Minimum subtitle display duration
    "max_duration": 4.0              # Maximum subtitle display duration
}


def check_whisper_installed() -> bool:
    """Check if openai-whisper is installed."""
    try:
        import whisper
        return True
    except ImportError:
        return False


def extract_word_timestamps_sync(
    audio_path: str,
    model_size: str = "base",
    language: str = "tr"
) -> Dict[str, Any]:
    """
    Extract word-level timestamps from audio using Whisper (synchronous).

    Args:
        audio_path: Path to audio file (MP3, WAV, etc.)
        model_size: Whisper model size (tiny, base, small, medium, large)
        language: Language code (tr for Turkish)

    Returns:
        {
            "success": bool,
            "words": [{"word": str, "start": float, "end": float}, ...],
            "segments": [{"text": str, "start": float, "end": float}, ...],
            "full_text": str,
            "duration": float,
            "error": str (if failed)
        }
    """
    if not os.path.exists(audio_path):
        return {"success": False, "error": f"Audio file not found: {audio_path}"}

    if not check_whisper_installed():
        return {"success": False, "error": "openai-whisper not installed. Run: pip install openai-whisper"}

    print(f"[WHISPER] Extracting timestamps from: {audio_path}")
    print(f"[WHISPER] Model: {model_size}, Language: {language}")

    try:
        import whisper

        # Load model (cached after first load)
        model = whisper.load_model(model_size)

        # Transcribe with word-level timestamps
        result = model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            verbose=False
        )

        # Extract words from all segments
        words = []
        for segment in result.get("segments", []):
            for word_info in segment.get("words", []):
                words.append({
                    "word": word_info["word"].strip(),
                    "start": word_info["start"],
                    "end": word_info["end"]
                })

        # Get segments (sentence-level)
        segments = [
            {
                "text": seg["text"].strip(),
                "start": seg["start"],
                "end": seg["end"]
            }
            for seg in result.get("segments", [])
        ]

        # Calculate duration
        duration = segments[-1]["end"] if segments else 0.0

        print(f"[WHISPER] Extracted {len(words)} words, {len(segments)} segments")

        return {
            "success": True,
            "words": words,
            "segments": segments,
            "full_text": result.get("text", ""),
            "duration": duration
        }

    except Exception as e:
        print(f"[WHISPER] Error: {e}")
        return {"success": False, "error": str(e)}


async def extract_word_timestamps(
    audio_path: str,
    model_size: str = "base",
    language: str = "tr"
) -> Dict[str, Any]:
    """
    Extract word-level timestamps from audio using Whisper (async wrapper).

    Runs the CPU-intensive Whisper transcription in a thread pool to avoid
    blocking the async event loop.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        extract_word_timestamps_sync,
        audio_path,
        model_size,
        language
    )


def group_words_into_sentences(
    words: List[Dict],
    max_chars: int = 35,
    max_lines: int = 2,
    min_duration: float = 1.0,
    max_duration: float = 4.0
) -> List[Dict]:
    """
    Group words into subtitle sentences optimized for readability.

    Creates sentence-based subtitles that break at natural points
    (punctuation, duration limits, character limits).

    Args:
        words: List of word dicts with start/end times
        max_chars: Maximum characters per line
        max_lines: Maximum lines per subtitle (1-3)
        min_duration: Minimum subtitle display duration
        max_duration: Maximum subtitle display duration

    Returns:
        List of subtitle entries:
        [
            {
                "text": "Subtitle text here",
                "start": 0.0,
                "end": 2.5,
                "lines": ["Line 1", "Line 2"]
            },
            ...
        ]
    """
    if not words:
        return []

    subtitles = []
    current_words = []
    current_text = ""

    # Turkish sentence-ending punctuation
    sentence_enders = ".!?"

    for word in words:
        word_text = word["word"].strip()
        if not word_text:
            continue

        # Check if adding this word exceeds limits
        test_text = (current_text + " " + word_text).strip()

        # Calculate how many lines would be needed
        total_chars = len(test_text)
        lines_needed = (total_chars + max_chars - 1) // max_chars

        # Check current duration
        if current_words:
            current_duration = word["end"] - current_words[0]["start"]
        else:
            current_duration = 0

        # Decide whether to start a new subtitle
        should_break = False

        # Break if too many lines needed
        if lines_needed > max_lines:
            should_break = True

        # Break if duration exceeded (but keep at least 2 words)
        if current_duration > max_duration and len(current_words) >= 2:
            should_break = True

        # Break at sentence boundaries (Turkish punctuation)
        if current_text and current_text.rstrip()[-1:] in sentence_enders:
            should_break = True

        if should_break and current_words:
            # Finalize current subtitle
            subtitles.append({
                "text": current_text.strip(),
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
                "lines": split_into_lines(current_text.strip(), max_chars)
            })
            current_words = []
            current_text = ""

        # Add word to current group
        current_words.append(word)
        current_text = (current_text + " " + word_text).strip()

    # Add remaining words
    if current_words:
        subtitles.append({
            "text": current_text.strip(),
            "start": current_words[0]["start"],
            "end": current_words[-1]["end"],
            "lines": split_into_lines(current_text.strip(), max_chars)
        })

    # Ensure minimum duration for each subtitle
    for sub in subtitles:
        if sub["end"] - sub["start"] < min_duration:
            sub["end"] = sub["start"] + min_duration

    # Prevent overlap between subtitles
    for i in range(len(subtitles) - 1):
        if subtitles[i]["end"] > subtitles[i + 1]["start"]:
            # Adjust end time to not overlap with next subtitle
            subtitles[i]["end"] = subtitles[i + 1]["start"] - 0.05

    return subtitles


def split_into_lines(text: str, max_chars: int = 35) -> List[str]:
    """
    Split text into balanced lines for subtitle display.

    Tries to break at natural points (spaces) while keeping
    lines roughly equal length for better visual appearance.

    Args:
        text: Text to split
        max_chars: Maximum characters per line

    Returns:
        List of lines (max 2-3)
    """
    text = text.strip()

    # Short text: single line
    if len(text) <= max_chars:
        return [text]

    words = text.split()

    # Two lines: try to balance
    if len(text) <= max_chars * 2:
        mid_point = len(text) // 2
        best_split = 0
        best_diff = len(text)

        current_len = 0
        for i, word in enumerate(words):
            current_len += len(word) + (1 if i > 0 else 0)
            diff = abs(current_len - mid_point)
            if diff < best_diff and current_len <= max_chars:
                best_diff = diff
                best_split = i + 1

        if best_split > 0 and best_split < len(words):
            line1 = " ".join(words[:best_split])
            line2 = " ".join(words[best_split:])
            if len(line1) <= max_chars and len(line2) <= max_chars:
                return [line1, line2]

    # Fallback: simple line-by-line split
    lines = []
    current_line = ""

    for word in words:
        if len(current_line) + len(word) + 1 <= max_chars:
            current_line = (current_line + " " + word).strip()
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines[:3]  # Max 3 lines


def format_ass_time(seconds: float) -> str:
    """
    Convert seconds to ASS timestamp format (H:MM:SS.cs).

    ASS uses centiseconds (1/100th of a second) for timing.

    Args:
        seconds: Time in seconds (float)

    Returns:
        ASS formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def generate_ass_subtitle(
    subtitles: List[Dict],
    config: Optional[Dict] = None,
    video_width: int = 720,
    video_height: int = 1280
) -> str:
    """
    Generate ASS subtitle file content.

    Creates a complete ASS (Advanced SubStation Alpha) subtitle file
    with Instagram/TikTok style formatting.

    Args:
        subtitles: List of subtitle entries from group_words_into_sentences
        config: Style configuration dict (uses defaults if None)
        video_width: Video width in pixels (default 720 for Instagram)
        video_height: Video height in pixels (default 1280 for Instagram)

    Returns:
        Complete ASS file content as string
    """
    cfg = {**DEFAULT_SUBTITLE_CONFIG, **(config or {})}

    # ASS uses -1 for bold, 0 for normal
    bold_flag = -1 if cfg["bold"] else 0

    # ASS Header
    ass_content = f"""[Script Info]
Title: Olivenet Auto Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{cfg['font_name']},{cfg['font_size']},{cfg['primary_color']},&H000000FF,{cfg['outline_color']},&H00000000,{bold_flag},0,0,0,100,100,0,0,1,{cfg['outline_width']},{cfg['shadow']},{cfg['alignment']},20,20,{cfg['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Add dialogue events for each subtitle
    for sub in subtitles:
        start_time = format_ass_time(sub["start"])
        end_time = format_ass_time(sub["end"])

        # Join lines with \N for ASS line breaks
        text = "\\N".join(sub["lines"])

        # Escape special ASS characters
        text = text.replace("{", "\\{").replace("}", "\\}")

        ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n"

    return ass_content


async def create_subtitle_file(
    audio_path: str,
    output_path: Optional[str] = None,
    model_size: str = "base",
    language: str = "tr",
    config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Full pipeline: Extract timestamps from audio and generate ASS file.

    This is the main entry point for subtitle generation. It:
    1. Runs Whisper transcription to get word-level timestamps
    2. Groups words into readable sentences
    3. Generates an ASS subtitle file

    Args:
        audio_path: Path to audio file (MP3, WAV, etc.)
        output_path: Output ASS file path (auto-generated if None)
        model_size: Whisper model size (tiny, base, small, medium, large)
        language: Language code (tr for Turkish)
        config: Subtitle style configuration dict

    Returns:
        {
            "success": bool,
            "ass_path": str,
            "subtitle_count": int,
            "duration": float,
            "full_text": str,
            "error": str (if failed)
        }
    """
    # Ensure output directory exists
    SUBTITLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[SUBTITLE] Starting subtitle generation for: {audio_path}")

    # Step 1: Extract word timestamps using Whisper
    whisper_result = await extract_word_timestamps(
        audio_path=audio_path,
        model_size=model_size,
        language=language
    )

    if not whisper_result.get("success"):
        return {
            "success": False,
            "error": f"Whisper transcription failed: {whisper_result.get('error')}"
        }

    # Step 2: Group words into sentences
    subtitle_config = {**DEFAULT_SUBTITLE_CONFIG, **(config or {})}
    subtitles = group_words_into_sentences(
        words=whisper_result["words"],
        max_chars=subtitle_config.get("max_chars_per_line", 35),
        max_lines=subtitle_config.get("max_lines", 2),
        min_duration=subtitle_config.get("min_duration", 1.0),
        max_duration=subtitle_config.get("max_duration", 4.0)
    )

    if not subtitles:
        return {
            "success": False,
            "error": "No subtitles generated from transcription"
        }

    # Step 3: Generate ASS content
    ass_content = generate_ass_subtitle(subtitles, subtitle_config)

    # Step 4: Write to file
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(SUBTITLE_OUTPUT_DIR / f"subs_{timestamp}.ass")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"[SUBTITLE] Created ASS file: {output_path}")
    print(f"[SUBTITLE] Subtitle count: {len(subtitles)}")
    print(f"[SUBTITLE] Duration: {whisper_result['duration']:.1f}s")

    return {
        "success": True,
        "ass_path": output_path,
        "subtitle_count": len(subtitles),
        "duration": whisper_result["duration"],
        "full_text": whisper_result.get("full_text", "")
    }


def create_subtitle_file_sync(
    audio_path: str,
    output_path: Optional[str] = None,
    model_size: str = "base",
    language: str = "tr",
    config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Synchronous version of create_subtitle_file for non-async contexts.
    """
    return asyncio.run(create_subtitle_file(
        audio_path=audio_path,
        output_path=output_path,
        model_size=model_size,
        language=language,
        config=config
    ))


# Quick test function
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python subtitle_helper.py <audio_path>")
        print("Example: python subtitle_helper.py outputs/audio/tts_xxx.mp3")
        sys.exit(1)

    audio_file = sys.argv[1]
    result = create_subtitle_file_sync(audio_file)

    if result["success"]:
        print(f"\nSuccess! ASS file: {result['ass_path']}")
        print(f"Subtitles: {result['subtitle_count']}")
        print(f"Duration: {result['duration']:.1f}s")
    else:
        print(f"\nError: {result['error']}")
