"""
Test TTS Pronunciation Fix + Subtitle Pipeline

Tests:
1. TTS pronunciation (MQTT, API, AI, IoT - no pauses)
2. Subtitle generation (Whisper hybrid)
3. Audio-video merge with existing Kling video
4. Subtitle burn into video

Does NOT publish to Instagram.
"""

import asyncio
import sys
import os

sys.path.insert(0, "/opt/olivenet-social-bot")


def load_env(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_env("/opt/olivenet-social-bot/.env")

from app.openai_tts_helper import generate_speech_with_retry, fix_pronunciation
from app.subtitle_helper import create_subtitle_file
from app.instagram_helper import (
    merge_audio_video,
    add_subtitles_to_video,
    get_video_duration,
    get_audio_duration,
)

VIDEO_PATH = "/opt/olivenet-social-bot/outputs/kling_20260321_102758_366422_4d4645.mp4"

TEST_SCRIPT = (
    "IoT cihaz filonuzu ilk günden itibaren güvenle yönetmenin yolu, "
    "doğru mimari kararlardan geçiyor. MQTT protokolü ile API altyapısı "
    "birleştiğinde, AI tabanlı analiz saniyeler içinde sonuç üretiyor."
)


async def main():
    print("=" * 60)
    print("TEST: TTS PRONUNCIATION FIX + SUBTITLE PIPELINE")
    print("=" * 60)

    # Step 0: Show pronunciation fixes
    print("\n[0/5] Telaffuz duzeltmeleri kontrol...")
    fixed = fix_pronunciation(TEST_SCRIPT)
    print(f"  Orijinal : {TEST_SCRIPT}")
    print(f"  Duzeltilmis: {fixed}")

    # Step 1: Check video file
    print("\n[1/5] Video dosya kontrolu...")
    if not os.path.exists(VIDEO_PATH):
        print(f"HATA: Video bulunamadi: {VIDEO_PATH}")
        return
    video_dur = await get_video_duration(VIDEO_PATH)
    print(f"  Video suresi: {video_dur:.1f}s")

    # Step 2: Generate TTS
    print("\n[2/5] TTS uretiliyor...")
    tts_result = await generate_speech_with_retry(text=TEST_SCRIPT, max_retries=2)
    if not tts_result.get("success"):
        print(f"HATA: TTS basarisiz: {tts_result.get('error')}")
        return
    audio_path = tts_result["audio_path"]
    audio_dur = await get_audio_duration(audio_path)
    print(f"  Audio: {audio_path}")
    print(f"  Sure: {audio_dur:.1f}s")

    # Step 3: Merge audio + video
    print("\n[3/5] Audio-video birlestiriliyor...")
    merge_result = await merge_audio_video(
        video_path=VIDEO_PATH,
        audio_path=audio_path,
        fade_out=True,
    )
    if not merge_result.get("success"):
        print(f"HATA: Merge basarisiz: {merge_result.get('error')}")
        return
    merged_path = merge_result["output_path"]
    print(f"  Merged: {merged_path}")
    print(f"  Sure: {merge_result.get('duration', 0):.1f}s")
    print(f"  Strateji: {merge_result.get('strategy')}")

    # Step 4: Create subtitles
    print("\n[4/5] Whisper ile altyazi olusturuluyor...")
    sub_result = await create_subtitle_file(
        audio_path=audio_path,
        original_script=TEST_SCRIPT,
        model_size="base",
        language="tr",
    )
    if not sub_result.get("success"):
        print(f"HATA: Altyazi olusturulamadi: {sub_result.get('error')}")
        return
    ass_path = sub_result["ass_path"]
    print(f"  ASS: {ass_path}")
    print(f"  Altyazi sayisi: {sub_result.get('subtitle_count')}")

    # Step 5: Burn subtitles
    print("\n[5/5] Altyazilar videoya yakiliyor...")
    burn_result = await add_subtitles_to_video(
        video_path=merged_path,
        ass_path=ass_path,
    )
    if not burn_result.get("success"):
        print(f"HATA: Altyazi yakma basarisiz: {burn_result.get('error')}")
        return
    final_path = burn_result["output_path"]
    print(f"  Final video: {final_path}")
    print(f"  Boyut: {burn_result.get('file_size_mb', 0):.1f}MB")

    print(f"\n{'=' * 60}")
    print("BASARILI! Test tamamlandi.")
    print(f"  Final video: {final_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
