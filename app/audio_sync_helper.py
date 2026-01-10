"""
Audio/Video Sync Helper - Akıllı audio senkronizasyonu

Video loop yapmadan audio'yu video süresine adapte eder:
- Küçük fark (≤1s): Trim + fade out
- Orta fark (≤3s): Trim + warning
- Büyük fark (>3s): TTS regenerate önerilir

CTA (son cümle) ve Hook (ilk cümle) korunmaya çalışılır.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

# Output directory
AUDIO_OUTPUT_DIR = Path("/opt/olivenet-social-bot/outputs/audio")


async def get_audio_duration(audio_path: str) -> float:
    """Audio süresini FFprobe ile al."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Audio duration error: {e}")
        return 0.0


async def trim_audio_with_fadeout(
    audio_path: str,
    target_duration: float,
    fade_duration: float = 0.5
) -> str:
    """
    Audio'yu hedef süreye kırp ve fade out ekle.

    Args:
        audio_path: Kaynak audio
        target_duration: Hedef süre (saniye)
        fade_duration: Fade out süresi (saniye)

    Returns:
        Kırpılmış audio dosya yolu
    """
    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = str(AUDIO_OUTPUT_DIR / f"trimmed_{timestamp}.mp3")

    # Fade out başlangıç zamanı
    fade_start = max(0, target_duration - fade_duration)

    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-af", f"afade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}",
        "-t", str(target_duration),
        "-c:a", "libmp3lame",
        "-q:a", "2",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"FFmpeg trim error: {result.stderr[:200]}")
            return audio_path  # Fallback: original

        logger.info(f"[AUDIO SYNC] Trimmed to {target_duration:.1f}s with {fade_duration}s fade")
        return output_path
    except Exception as e:
        logger.error(f"Trim exception: {e}")
        return audio_path


def shorten_script(script: str, target_duration: float, words_per_second: float = 2.5) -> str:
    """
    Script'i hedef süreye göre kısalt.

    Strateji: Hook (ilk cümle) ve CTA (son cümle) korunur, ortadan kısaltılır.

    Args:
        script: Orijinal script
        target_duration: Hedef süre (saniye)
        words_per_second: Ortalama konuşma hızı

    Returns:
        Kısaltılmış script
    """
    target_words = int(target_duration * words_per_second)
    words = script.split()

    if len(words) <= target_words:
        return script

    # Cümlelere ayır
    sentences = []
    current = []
    for word in words:
        current.append(word)
        if word.endswith('.') or word.endswith('!') or word.endswith('?'):
            sentences.append(' '.join(current))
            current = []
    if current:
        sentences.append(' '.join(current))

    if len(sentences) < 2:
        # Tek cümle - basit kırp
        return ' '.join(words[:target_words])

    # Hook (ilk cümle) ve CTA (son cümle) korunur
    hook = sentences[0]
    cta = sentences[-1]
    middle_sentences = sentences[1:-1]

    hook_words = len(hook.split())
    cta_words = len(cta.split())
    available_for_middle = target_words - hook_words - cta_words

    if available_for_middle <= 0:
        # Hook + CTA bile fazla, sadece hook + CTA
        logger.warning("[SCRIPT] Hook + CTA yeterli, orta kısım çıkarıldı")
        return f"{hook} {cta}"

    # Ortadaki cümleleri kısalt
    middle_text = ' '.join(middle_sentences)
    middle_words = middle_text.split()
    shortened_middle = ' '.join(middle_words[:available_for_middle])

    result = f"{hook} {shortened_middle} {cta}"
    logger.info(f"[SCRIPT] Kısaltıldı: {len(words)} → {len(result.split())} kelime")

    return result


async def sync_audio_to_video(
    audio_path: str,
    video_duration: float,
    original_script: Optional[str] = None,
    tts_regenerate_callback: Optional[Callable] = None,
    max_trim_without_warning: float = 1.0,
    max_trim_with_warning: float = 3.0
) -> Dict[str, Any]:
    """
    Audio'yu video süresine senkronize et.

    Video loop YAPMAZ - bunun yerine audio'yu adapte eder.

    Args:
        audio_path: Kaynak audio dosyası
        video_duration: Video süresi (saniye)
        original_script: TTS için kullanılan orijinal script
        tts_regenerate_callback: TTS yeniden üretmek için async callback
        max_trim_without_warning: Uyarısız kırpma limiti (saniye)
        max_trim_with_warning: Uyarılı kırpma limiti (saniye)

    Returns:
        {
            "success": bool,
            "audio_path": str,
            "action": "none" | "trim_small" | "trim_medium" | "trim_large" | "regenerate",
            "original_duration": float,
            "final_duration": float,
            "trimmed_seconds": float
        }
    """
    if not os.path.exists(audio_path):
        return {"success": False, "error": f"Audio bulunamadı: {audio_path}"}

    audio_duration = await get_audio_duration(audio_path)
    if audio_duration <= 0:
        return {"success": False, "error": "Audio süresi alınamadı"}

    diff = audio_duration - video_duration

    print(f"[AUDIO SYNC] Audio: {audio_duration:.1f}s, Video: {video_duration:.1f}s, Fark: {diff:.1f}s")

    # Audio <= Video: Sorun yok
    if diff <= 0:
        print("[AUDIO SYNC] ✓ Audio ≤ Video, senkronizasyon gerekmiyor")
        return {
            "success": True,
            "audio_path": audio_path,
            "action": "none",
            "original_duration": audio_duration,
            "final_duration": audio_duration,
            "trimmed_seconds": 0
        }

    # Küçük fark (≤1s): Sessiz trim
    if diff <= max_trim_without_warning:
        trimmed_path = await trim_audio_with_fadeout(audio_path, video_duration)
        print(f"[AUDIO SYNC] ✓ Küçük fark ({diff:.1f}s), trim yapıldı")
        return {
            "success": True,
            "audio_path": trimmed_path,
            "action": "trim_small",
            "original_duration": audio_duration,
            "final_duration": video_duration,
            "trimmed_seconds": diff
        }

    # Orta fark (≤3s): Trim + warning
    if diff <= max_trim_with_warning:
        trimmed_path = await trim_audio_with_fadeout(audio_path, video_duration)
        logger.warning(f"[AUDIO SYNC] ⚠️ Orta fark ({diff:.1f}s) kırpıldı, CTA etkilenmiş olabilir")
        print(f"[AUDIO SYNC] ⚠️ Orta fark ({diff:.1f}s), trim + warning")
        return {
            "success": True,
            "audio_path": trimmed_path,
            "action": "trim_medium",
            "original_duration": audio_duration,
            "final_duration": video_duration,
            "trimmed_seconds": diff
        }

    # Büyük fark (>3s): TTS regenerate öner veya zorla trim
    print(f"[AUDIO SYNC] ⛔ Büyük fark ({diff:.1f}s)")

    # TTS regenerate callback varsa ve script varsa
    if tts_regenerate_callback and original_script:
        try:
            # Script'i kısalt
            shorter_script = shorten_script(original_script, video_duration)
            print(f"[AUDIO SYNC] Script kısaltıldı, TTS yeniden üretiliyor...")

            # TTS yeniden üret
            new_audio_result = await tts_regenerate_callback(shorter_script)

            if new_audio_result and new_audio_result.get("success"):
                new_audio_path = new_audio_result.get("audio_path")
                new_duration = await get_audio_duration(new_audio_path)

                print(f"[AUDIO SYNC] ✓ TTS regenerate başarılı: {new_duration:.1f}s")

                # Hala uzunsa trim yap
                if new_duration > video_duration:
                    new_audio_path = await trim_audio_with_fadeout(new_audio_path, video_duration)
                    new_duration = video_duration

                return {
                    "success": True,
                    "audio_path": new_audio_path,
                    "action": "regenerate",
                    "original_duration": audio_duration,
                    "final_duration": new_duration,
                    "trimmed_seconds": audio_duration - new_duration,
                    "regenerated_script": shorter_script
                }
        except Exception as e:
            logger.error(f"[AUDIO SYNC] TTS regenerate hatası: {e}")
            print(f"[AUDIO SYNC] TTS regenerate başarısız, trim'e düşülüyor")

    # Fallback: Zorla trim (uyarı ile)
    trimmed_path = await trim_audio_with_fadeout(audio_path, video_duration)
    logger.error(f"[AUDIO SYNC] ⛔ Büyük fark ({diff:.1f}s) zorla kırpıldı! İçerik kaybı olabilir")
    print(f"[AUDIO SYNC] ⛔ Büyük fark zorla kırpıldı ({diff:.1f}s)")

    return {
        "success": True,
        "audio_path": trimmed_path,
        "action": "trim_large",
        "original_duration": audio_duration,
        "final_duration": video_duration,
        "trimmed_seconds": diff,
        "warning": f"Büyük fark ({diff:.1f}s) zorla kırpıldı, CTA kaybı olabilir"
    }
