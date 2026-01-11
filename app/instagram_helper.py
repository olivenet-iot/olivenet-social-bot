"""
Instagram Helper - Instagram Graph API Entegrasyonu
Yeni API: graph.instagram.com v21.0 (Instagram Login)
"""

import os
import asyncio
import aiohttp
import subprocess
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("instagram")

# Instagram Graph API URL (YENİ - graph.instagram.com)
GRAPH_API_URL = "https://graph.instagram.com/v21.0"

# Video conversion output directory
OUTPUT_DIR = str(settings.outputs_dir)


def get_instagram_credentials() -> Dict[str, str]:
    """Instagram API credentials'ları al"""
    return {
        "access_token": os.getenv("INSTAGRAM_ACCESS_TOKEN", ""),
        "user_id": os.getenv("INSTAGRAM_USER_ID", ""),
        "business_id": os.getenv("INSTAGRAM_BUSINESS_ID", "")
    }


async def convert_video_for_instagram(input_path: str) -> Dict[str, Any]:
    """
    Video'yu Instagram Reels formatına dönüştür

    Instagram Gereksinimleri:
    - Codec: H.264 (video), AAC (audio)
    - Çözünürlük: 720x1280 (9:16)
    - FPS: 30
    - Max süre: 90 saniye
    - Format: MP4
    """
    if not os.path.exists(input_path):
        return {"success": False, "error": f"Video bulunamadı: {input_path}"}

    print(f"[VIDEO CONVERT] Kaynak: {input_path}")

    # ffmpeg kontrolü
    try:
        result = subprocess.run(["which", "ffmpeg"], capture_output=True)
        if result.returncode != 0:
            print("[VIDEO CONVERT] ffmpeg yüklü değil!")
            return {"success": False, "error": "ffmpeg not installed"}
    except Exception as e:
        return {"success": False, "error": f"ffmpeg check failed: {e}"}

    # Video bilgilerini al
    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate",
            "-of", "csv=p=0",
            input_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        probe_output = probe_result.stdout.strip()
        print(f"[VIDEO CONVERT] Probe: {probe_output}")

        parts = probe_output.split(",")
        if len(parts) >= 4:
            codec = parts[0]
            width = int(parts[1])
            height = int(parts[2])
            fps_str = parts[3]

            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = int(num) / int(den) if int(den) > 0 else 30
            else:
                fps = float(fps_str)

            print(f"[VIDEO CONVERT] Codec: {codec}, Size: {width}x{height}, FPS: {fps:.1f}")

            is_compatible = (
                codec == "h264" and
                width == 720 and
                height == 1280 and
                abs(fps - 30) < 1
            )

            if is_compatible:
                print("[VIDEO CONVERT] Video zaten Instagram uyumlu!")
                return {
                    "success": True,
                    "output_path": input_path,
                    "converted": False,
                    "original_codec": codec,
                    "original_size": f"{width}x{height}"
                }
    except Exception as e:
        print(f"[VIDEO CONVERT] Probe hatası: {e}")

    # Dönüştürülmüş dosya yolu
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{OUTPUT_DIR}/ig_ready_{timestamp}.mp4"

    print(f"[VIDEO CONVERT] Dönüştürülüyor: {output_path}")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-r", "30",
        "-movflags", "+faststart",
        "-t", "90",
        output_path
    ]

    try:
        process = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if process.returncode != 0:
            print(f"[VIDEO CONVERT] ffmpeg hatası: {process.stderr[:500]}")
            return {"success": False, "error": f"ffmpeg error: {process.stderr[:200]}"}

        if not os.path.exists(output_path):
            return {"success": False, "error": "Output file not created"}

        file_size = os.path.getsize(output_path) / 1024 / 1024
        print(f"[VIDEO CONVERT] Başarılı! Boyut: {file_size:.2f} MB")

        return {
            "success": True,
            "output_path": output_path,
            "converted": True,
            "file_size_mb": round(file_size, 2)
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "ffmpeg timeout (5 min)"}
    except Exception as e:
        print(f"[VIDEO CONVERT] Exception: {e}")
        return {"success": False, "error": str(e)}


async def get_audio_duration(audio_path: str) -> float:
    """
    Audio dosyasının süresini al

    Args:
        audio_path: Audio dosya yolu

    Returns:
        Süre (saniye) veya 0.0 hata durumunda
    """
    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            audio_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration_str = result.stdout.strip()
        return float(duration_str) if duration_str else 0.0
    except Exception as e:
        print(f"[AUDIO PROBE] Hata: {e}")
        return 0.0


async def get_video_duration(video_path: str) -> float:
    """
    Video dosyasının süresini al

    Args:
        video_path: Video dosya yolu

    Returns:
        Süre (saniye) veya 0.0 hata durumunda
    """
    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            video_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration_str = result.stdout.strip()
        return float(duration_str) if duration_str else 0.0
    except Exception as e:
        print(f"[VIDEO PROBE] Hata: {e}")
        return 0.0


async def merge_audio_video(
    video_path: str,
    audio_path: str,
    target_duration: Optional[float] = None,
    audio_volume: float = 1.0,
    fade_out: bool = True,
    fade_duration: float = 0.5,  # 0.5s fade-out - audio kesilse bile yumuşak biter
    keep_video_duration: bool = False  # Video süresini koru, audio kısaysa sorun yok
) -> Dict[str, Any]:
    """
    Video ve audio dosyalarını birleştir.

    Instagram Reels gereksinimleri:
    - H.264 video, AAC audio
    - 720x1280 (9:16)
    - 30 FPS
    - Max 90 saniye

    Strateji:
    1. Audio süresi > Video süresi: Video'yu loop et
    2. Video süresi > Audio süresi: Video'yu audio süresine kırp + fade out
    3. keep_video_duration=True: Video süresini koru, audio kısaysa sessiz kal

    Args:
        video_path: Kaynak video
        audio_path: Kaynak audio (MP3/AAC)
        target_duration: Hedef süre (None ise audio süresine göre)
        audio_volume: Ses seviyesi (0.0-2.0)
        fade_out: Video sonunda fade-out efekti
        fade_duration: Fade-out süresi (saniye)
        keep_video_duration: Video süresini koru (B-roll için)

    Returns:
        {
            "success": bool,
            "output_path": str,
            "duration": float,
            "file_size_mb": float,
            "strategy": str  # "trim_video", "loop_video", "keep_video"
        }
    """
    if not os.path.exists(video_path):
        return {"success": False, "error": f"Video bulunamadı: {video_path}"}

    if not os.path.exists(audio_path):
        return {"success": False, "error": f"Audio bulunamadı: {audio_path}"}

    print(f"[AUDIO-VIDEO MERGE] Video: {video_path}")
    print(f"[AUDIO-VIDEO MERGE] Audio: {audio_path}")

    # Süreleri al
    video_duration = await get_video_duration(video_path)
    audio_duration = await get_audio_duration(audio_path)

    if video_duration <= 0:
        return {"success": False, "error": "Video süresi alınamadı"}

    if audio_duration <= 0:
        return {"success": False, "error": "Audio süresi alınamadı"}

    print(f"[AUDIO-VIDEO MERGE] Video süresi: {video_duration:.1f}s")
    print(f"[AUDIO-VIDEO MERGE] Audio süresi: {audio_duration:.1f}s")

    # Hedef süreyi belirle
    if target_duration:
        final_duration = min(target_duration, 90.0)  # Instagram max 90s
    else:
        final_duration = min(audio_duration, 90.0)

    print(f"[AUDIO-VIDEO MERGE] Hedef süre: {final_duration:.1f}s")

    # Strateji belirle
    # Küçük fark toleransı (3 saniye) - gereksiz loop önlemek için
    LOOP_TOLERANCE = 3.0
    duration_diff = final_duration - video_duration

    if keep_video_duration:
        # B-roll için: Video süresini koru, audio kısaysa sorun yok
        strategy = "keep_video"
        loop_video = False
        final_duration = min(video_duration, 90.0)  # Video süresini kullan
        print(f"[AUDIO-VIDEO MERGE] Strateji: keep_video (video {video_duration:.1f}s korunuyor, audio {audio_duration:.1f}s)")
    elif video_duration >= final_duration:
        # Video yeterince uzun, kırp
        strategy = "trim_video"
        loop_video = False
        print(f"[AUDIO-VIDEO MERGE] Strateji: trim_video (video {video_duration:.1f}s >= hedef {final_duration:.1f}s)")
    elif duration_diff <= LOOP_TOLERANCE:
        # Fark küçük, loop yapma - -shortest kullan
        strategy = "shortest"
        loop_video = False
        print(f"[AUDIO-VIDEO MERGE] Strateji: shortest (fark {duration_diff:.1f}s <= tolerans {LOOP_TOLERANCE}s)")
    else:
        # Fark büyük, loop gerekli
        strategy = "loop_video"
        loop_video = True
        loop_count = int(final_duration / video_duration) + 1
        print(f"[AUDIO-VIDEO MERGE] Strateji: loop_video ({loop_count}x loop, fark {duration_diff:.1f}s)")

    # Output dosyası
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{OUTPUT_DIR}/merged_{timestamp}.mp4"

    # FFmpeg komutu oluştur
    ffmpeg_cmd = ["ffmpeg", "-y"]

    # Video input (audio disabled - TTS audio kullanılacak)
    if loop_video:
        ffmpeg_cmd.extend(["-stream_loop", "-1"])
    ffmpeg_cmd.extend(["-an", "-i", video_path])  # -an: video'nun kendi sesini ignore et

    # Audio input (TTS)
    ffmpeg_cmd.extend(["-i", audio_path])

    # Video codec
    ffmpeg_cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23"
    ])

    # Audio codec
    ffmpeg_cmd.extend([
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100"
    ])

    # Video filter (scale + pad + fade)
    vf_parts = [
        "scale=720:1280:force_original_aspect_ratio=decrease",
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2",
        "setsar=1"
    ]

    # Fade-out efekti
    if fade_out and final_duration > fade_duration:
        fade_start = final_duration - fade_duration
        vf_parts.append(f"fade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}")

    ffmpeg_cmd.extend(["-vf", ",".join(vf_parts)])

    # Audio filter (volume + fade)
    af_parts = []
    if audio_volume != 1.0:
        af_parts.append(f"volume={audio_volume}")
    if fade_out and final_duration > fade_duration:
        fade_start = final_duration - fade_duration
        af_parts.append(f"afade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}")

    if af_parts:
        ffmpeg_cmd.extend(["-af", ",".join(af_parts)])

    # Frame rate
    ffmpeg_cmd.extend(["-r", "30"])

    # Duration limit
    if strategy == "shortest":
        # Küçük fark - en kısa stream bitince dur (loop yok)
        ffmpeg_cmd.extend(["-shortest"])
    else:
        ffmpeg_cmd.extend(["-t", str(final_duration)])

    # Stream mapping
    ffmpeg_cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])

    # MP4 optimization
    ffmpeg_cmd.extend(["-movflags", "+faststart"])

    # Output
    ffmpeg_cmd.append(output_path)

    print(f"[AUDIO-VIDEO MERGE] FFmpeg komutu çalıştırılıyor...")
    print(f"[AUDIO-VIDEO MERGE] Strateji: {strategy}")

    try:
        process = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 dakika timeout
        )

        if process.returncode != 0:
            print(f"[AUDIO-VIDEO MERGE] FFmpeg hatası: {process.stderr[:500]}")
            return {"success": False, "error": f"FFmpeg error: {process.stderr[:200]}"}

        if not os.path.exists(output_path):
            return {"success": False, "error": "Output dosyası oluşturulamadı"}

        # Sonuç bilgileri
        file_size = os.path.getsize(output_path) / 1024 / 1024
        actual_duration = await get_video_duration(output_path)

        print(f"[AUDIO-VIDEO MERGE] Başarılı!")
        print(f"[AUDIO-VIDEO MERGE] Çıktı: {output_path}")
        print(f"[AUDIO-VIDEO MERGE] Süre: {actual_duration:.1f}s, Boyut: {file_size:.2f}MB")

        return {
            "success": True,
            "output_path": output_path,
            "duration": actual_duration,
            "file_size_mb": round(file_size, 2),
            "strategy": strategy
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "FFmpeg timeout (5 min)"}
    except Exception as e:
        print(f"[AUDIO-VIDEO MERGE] Exception: {e}")
        return {"success": False, "error": str(e)}


async def add_subtitles_to_video(
    video_path: str,
    ass_path: str,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Burn ASS subtitles into video using FFmpeg.

    Uses the 'ass' filter which provides better styling control than 'subtitles'.
    The ASS file must already exist with proper styling.

    Args:
        video_path: Input video file path
        ass_path: ASS subtitle file path
        output_path: Output file path (auto-generated if None)

    Returns:
        {
            "success": bool,
            "output_path": str,
            "file_size_mb": float,
            "error": str (if failed)
        }
    """
    if not os.path.exists(video_path):
        return {"success": False, "error": f"Video not found: {video_path}"}

    if not os.path.exists(ass_path):
        return {"success": False, "error": f"Subtitle file not found: {ass_path}"}

    # Generate output path if not provided
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{OUTPUT_DIR}/subtitled_{timestamp}.mp4"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"[SUBTITLE BURN] Input video: {video_path}")
    print(f"[SUBTITLE BURN] ASS file: {ass_path}")
    print(f"[SUBTITLE BURN] Output: {output_path}")

    # FFmpeg command with ASS filter
    # Note: For the ass filter, path needs proper escaping
    # Using colon and backslash escaping for FFmpeg filter syntax
    escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "'\\''")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass='{escaped_ass_path}'",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "copy",  # Copy audio stream unchanged
        "-movflags", "+faststart",
        output_path
    ]

    try:
        print(f"[SUBTITLE BURN] Running FFmpeg...")
        process = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if process.returncode != 0:
            error_msg = process.stderr[-500:] if len(process.stderr) > 500 else process.stderr
            print(f"[SUBTITLE BURN] FFmpeg error: {error_msg}")
            return {"success": False, "error": f"FFmpeg error: {error_msg[:200]}"}

        if not os.path.exists(output_path):
            return {"success": False, "error": "Output file not created"}

        file_size = os.path.getsize(output_path) / 1024 / 1024
        print(f"[SUBTITLE BURN] Success! Size: {file_size:.2f}MB")

        return {
            "success": True,
            "output_path": output_path,
            "file_size_mb": round(file_size, 2)
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "FFmpeg timeout (5 min)"}
    except Exception as e:
        print(f"[SUBTITLE BURN] Exception: {e}")
        return {"success": False, "error": str(e)}


def build_crossfade_filter(
    video_durations: List[float],
    crossfade_duration: float = 0.5
) -> str:
    """
    N video için FFmpeg crossfade filter_complex string'i oluştur (video + audio).

    Args:
        video_durations: Her videonun gerçek süresi (saniye listesi)
        crossfade_duration: Crossfade geçiş süresi (saniye)

    Returns:
        FFmpeg filter_complex string ([vout] ve [aout] output'ları ile)
    """
    video_count = len(video_durations)
    if video_count < 2:
        raise ValueError("En az 2 video gerekli")

    filter_parts = []

    # Her input için video scale ve format
    for i in range(video_count):
        filter_parts.append(
            f"[{i}:v]setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=decrease,"
            f"pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p[v{i}]"
        )

    # Her input için audio normalization
    for i in range(video_count):
        filter_parts.append(
            f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}]"
        )

    # Video ve Audio crossfade zincirleme
    if video_count == 2:
        # İlk videonun gerçek süresini kullan
        offset = video_durations[0] - crossfade_duration
        # Video crossfade
        filter_parts.append(
            f"[v0][v1]xfade=transition=fade:duration={crossfade_duration}:offset={offset:.2f}[vout]"
        )
        # Audio crossfade
        filter_parts.append(
            f"[a0][a1]acrossfade=d={crossfade_duration}:c1=tri:c2=tri[aout]"
        )
    else:
        # N video için zincirleme xfade
        current_v_output = "v0"
        current_a_output = "a0"
        cumulative_duration = video_durations[0]

        for i in range(1, video_count):
            offset = cumulative_duration - crossfade_duration
            next_v_output = "vout" if i == video_count - 1 else f"vt{i}"
            next_a_output = "aout" if i == video_count - 1 else f"at{i}"

            # Video xfade
            filter_parts.append(
                f"[{current_v_output}][v{i}]xfade=transition=fade:"
                f"duration={crossfade_duration}:offset={offset:.2f}[{next_v_output}]"
            )
            # Audio crossfade
            filter_parts.append(
                f"[{current_a_output}][a{i}]acrossfade=d={crossfade_duration}:c1=tri:c2=tri[{next_a_output}]"
            )

            current_v_output = next_v_output
            current_a_output = next_a_output
            # Sonraki video süresini ekle (crossfade çıkar)
            cumulative_duration += video_durations[i] - crossfade_duration

    return ";".join(filter_parts)


async def concatenate_videos_with_crossfade(
    video_paths: List[str],
    output_path: str = None,
    crossfade_duration: float = 0.5,
    segment_duration: float = 10.0
) -> Dict[str, Any]:
    """
    Birden fazla videoyu crossfade geçişlerle birleştir.

    Args:
        video_paths: Sıralı video dosya yolları listesi
        output_path: Çıktı dosya yolu (None ise otomatik oluşturulur)
        crossfade_duration: Crossfade süresi (saniye)
        segment_duration: Her segment'in yaklaşık süresi (saniye)

    Returns:
        {
            "success": bool,
            "output_path": str,
            "total_duration": float,
            "segment_count": int,
            "file_size_mb": float
        }
    """
    if len(video_paths) < 2:
        return {"success": False, "error": "En az 2 video gerekli"}

    if len(video_paths) > 6:
        return {"success": False, "error": "Maksimum 6 video destekleniyor"}

    # Tüm dosyaların var olduğunu kontrol et
    for path in video_paths:
        if not os.path.exists(path):
            return {"success": False, "error": f"Video bulunamadı: {path}"}

    # Output path
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(OUTPUT_DIR, f"concat_{timestamp}.mp4")

    # Output dizinini oluştur
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"[VIDEO CONCAT] {len(video_paths)} video birleştiriliyor...")
    print(f"[VIDEO CONCAT] Crossfade: {crossfade_duration}s")

    try:
        # Her videonun gerçek süresini al
        video_durations = []
        for path in video_paths:
            duration = await get_video_duration(path)
            if not duration:
                # Fallback: segment_duration kullan
                duration = segment_duration
                print(f"[VIDEO CONCAT] Uyarı: {path} süresi alınamadı, {segment_duration}s varsayıldı")
            video_durations.append(duration)

        print(f"[VIDEO CONCAT] Video süreleri: {video_durations}")

        # Filter complex oluştur (gerçek sürelerle)
        filter_complex = build_crossfade_filter(
            video_durations=video_durations,
            crossfade_duration=crossfade_duration
        )

        # FFmpeg komutu oluştur
        ffmpeg_cmd = ["ffmpeg", "-y"]

        # Input'lar
        for path in video_paths:
            ffmpeg_cmd.extend(["-i", path])

        # Filter complex
        ffmpeg_cmd.extend(["-filter_complex", filter_complex])

        # Output mapping ve codec (video + audio)
        ffmpeg_cmd.extend([
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            output_path
        ])

        print(f"[VIDEO CONCAT] FFmpeg çalıştırılıyor...")

        # FFmpeg çalıştır (5 dakika timeout)
        process = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if process.returncode != 0:
            print(f"[VIDEO CONCAT] FFmpeg hata: {process.stderr[:500]}")

            # Fallback: Simple concat (crossfade olmadan)
            print("[VIDEO CONCAT] Fallback: Simple concat deneniyor...")
            return await simple_concat_fallback(video_paths, output_path)

        # Çıktı kontrolü
        if not os.path.exists(output_path):
            return {"success": False, "error": "Çıktı dosyası oluşturulamadı"}

        # Dosya boyutu
        file_size = os.path.getsize(output_path) / (1024 * 1024)

        # Süre hesaplama (ffprobe ile)
        duration_result = await get_video_duration(output_path)
        total_duration = duration_result if duration_result else (
            len(video_paths) * segment_duration -
            (len(video_paths) - 1) * crossfade_duration
        )

        print(f"[VIDEO CONCAT] Başarılı!")
        print(f"[VIDEO CONCAT] Çıktı: {output_path}")
        print(f"[VIDEO CONCAT] Süre: {total_duration:.1f}s, Boyut: {file_size:.2f}MB")

        return {
            "success": True,
            "output_path": output_path,
            "total_duration": total_duration,
            "segment_count": len(video_paths),
            "file_size_mb": round(file_size, 2)
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "FFmpeg concat timeout (5 min)"}
    except Exception as e:
        print(f"[VIDEO CONCAT] Exception: {e}")
        return {"success": False, "error": str(e)}


async def simple_concat_fallback(
    video_paths: List[str],
    output_path: str
) -> Dict[str, Any]:
    """
    Crossfade başarısız olursa basit concat ile birleştir.
    """
    try:
        # Concat demuxer için liste dosyası oluştur
        list_path = output_path.replace(".mp4", "_list.txt")

        with open(list_path, "w") as f:
            for path in video_paths:
                f.write(f"file '{path}'\n")

        # Simple concat komutu
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-movflags", "+faststart",
            output_path
        ]

        process = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        # Liste dosyasını temizle
        if os.path.exists(list_path):
            os.remove(list_path)

        if process.returncode != 0:
            return {"success": False, "error": f"Simple concat de başarısız: {process.stderr[:200]}"}

        file_size = os.path.getsize(output_path) / (1024 * 1024)

        return {
            "success": True,
            "output_path": output_path,
            "total_duration": 0,  # Hesaplanmadı
            "segment_count": len(video_paths),
            "file_size_mb": round(file_size, 2),
            "fallback": True
        }

    except Exception as e:
        return {"success": False, "error": f"Fallback hata: {str(e)}"}


async def get_video_duration(video_path: str) -> Optional[float]:
    """FFprobe ile video süresini al"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


async def get_account_info() -> Dict[str, Any]:
    """
    Instagram hesap bilgilerini al

    Returns:
        {"id": "...", "username": "...", "media_count": N, "followers_count": N}
    """
    creds = get_instagram_credentials()

    if not creds["access_token"] or not creds["user_id"]:
        return {"success": False, "error": "Instagram credentials eksik"}

    url = f"{GRAPH_API_URL}/{creds['user_id']}"
    params = {
        "fields": "id,username,media_count,followers_count",
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

                if "error" in data:
                    print(f"[INSTAGRAM] API Error: {data['error'].get('message', 'Unknown')}")
                    return {"success": False, "error": data["error"].get("message")}

                print(f"[INSTAGRAM] Hesap: @{data.get('username')} | Takipçi: {data.get('followers_count', 0)}")
                return {"success": True, **data}

    except Exception as e:
        print(f"[INSTAGRAM] Connection error: {e}")
        return {"success": False, "error": str(e)}


async def create_media_container(
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    caption: str = "",
    media_type: str = "IMAGE",
    is_carousel_item: bool = False,
    max_retries: int = 3
) -> Optional[str]:
    """
    Instagram Media Container oluştur (2-aşamalı yükleme için)
    Retry mekanizması ile timeout hatalarını handle eder.

    Args:
        image_url: Görsel URL'i (public erişilebilir, direkt .jpg/.png)
        video_url: Video URL'i (public erişilebilir)
        caption: Post caption'ı
        media_type: IMAGE, REELS, veya CAROUSEL
        is_carousel_item: Carousel child item mi?
        max_retries: Maksimum deneme sayısı

    Returns:
        Container ID veya None
    """
    creds = get_instagram_credentials()

    if not creds["access_token"] or not creds["user_id"]:
        print("[INSTAGRAM] Credentials eksik!")
        return None

    url = f"{GRAPH_API_URL}/{creds['user_id']}/media"

    data = {
        "access_token": creds["access_token"]
    }

    # Carousel item değilse caption ekle
    if not is_carousel_item and caption:
        data["caption"] = caption

    # Media type'a göre URL ekle
    if media_type == "IMAGE":
        data["image_url"] = image_url
    elif media_type == "REELS":
        data["video_url"] = video_url
        data["media_type"] = "REELS"

    # Carousel item flag
    if is_carousel_item:
        data["is_carousel_item"] = "true"

    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(total=60)  # 30s → 60s
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, data=data) as response:
                    result = await response.json()

                    if "error" in result:
                        error_msg = result["error"].get("message", "Unknown error")
                        print(f"[INSTAGRAM] Container Error: {error_msg}")

                        # Retry edilebilir hata mı?
                        if "timeout" in error_msg.lower() or "rate" in error_msg.lower():
                            if attempt < max_retries - 1:
                                wait_time = 5 * (attempt + 1)
                                print(f"[INSTAGRAM] Retry {attempt + 1}/{max_retries}, {wait_time}s bekleniyor...")
                                await asyncio.sleep(wait_time)
                                continue
                        return None

                    container_id = result.get("id")
                    print(f"[INSTAGRAM] Media Container oluşturuldu: {container_id}")
                    return container_id

        except asyncio.TimeoutError:
            print(f"[INSTAGRAM] Container timeout (60s), retry {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)  # 5s, 10s, 15s
                await asyncio.sleep(wait_time)
            else:
                print("[INSTAGRAM] Max retries exceeded for container creation")
                return None

        except Exception as e:
            print(f"[INSTAGRAM] Container creation error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(3)
            else:
                return None

    return None


async def create_carousel_container(
    children_ids: List[str],
    caption: str = "",
    max_retries: int = 3
) -> Optional[str]:
    """
    Carousel ana container oluştur - retry ile

    Args:
        children_ids: Child container ID listesi
        caption: Post caption'ı
        max_retries: Maksimum deneme sayısı

    Returns:
        Carousel container ID veya None
    """
    creds = get_instagram_credentials()

    if not creds["access_token"] or not creds["user_id"]:
        return None

    url = f"{GRAPH_API_URL}/{creds['user_id']}/media"

    data = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": creds["access_token"]
    }

    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(total=60)  # 30s → 60s
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, data=data) as response:
                    result = await response.json()

                    if "error" in result:
                        error_msg = result["error"].get("message", "Unknown")
                        print(f"[INSTAGRAM] Carousel Container Error: {error_msg}")

                        if "timeout" in error_msg.lower() or "rate" in error_msg.lower():
                            if attempt < max_retries - 1:
                                wait_time = 5 * (attempt + 1)
                                print(f"[INSTAGRAM] Carousel retry {attempt + 1}/{max_retries}...")
                                await asyncio.sleep(wait_time)
                                continue
                        return None

                    container_id = result.get("id")
                    print(f"[INSTAGRAM] Carousel Container: {container_id}")
                    return container_id

        except asyncio.TimeoutError:
            print(f"[INSTAGRAM] Carousel container timeout, retry {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5 * (attempt + 1))
            else:
                return None

        except Exception as e:
            print(f"[INSTAGRAM] Carousel container error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(3)
            else:
                return None

    return None


async def check_container_status(container_id: str) -> Dict[str, Any]:
    """
    Media container durumunu kontrol et (video için gerekli)
    """
    creds = get_instagram_credentials()

    url = f"{GRAPH_API_URL}/{container_id}"
    params = {
        "fields": "status_code,status",
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                return await response.json()
    except Exception as e:
        return {"error": str(e)}


async def publish_media(container_id: str) -> Dict[str, Any]:
    """
    Media container'ı yayınla

    Args:
        container_id: Media container ID

    Returns:
        {"success": True, "id": "post_id"} veya {"success": False, "error": "..."}
    """
    creds = get_instagram_credentials()

    url = f"{GRAPH_API_URL}/{creds['user_id']}/media_publish"
    data = {
        "creation_id": container_id,
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                result = await response.json()

                if "error" in result:
                    error_msg = result["error"].get("message", "Unknown error")
                    print(f"[INSTAGRAM] Publish Error: {error_msg}")
                    return {"success": False, "error": error_msg}

                post_id = result.get("id")
                print(f"[INSTAGRAM] Post yayınlandı! ID: {post_id}")
                return {"success": True, "id": post_id}

    except Exception as e:
        print(f"[INSTAGRAM] Publish error: {e}")
        return {"success": False, "error": str(e)}


async def post_photo_to_instagram(
    image_url: str,
    caption: str = ""
) -> Dict[str, Any]:
    """
    Instagram'a fotoğraf paylaş

    Args:
        image_url: Görsel URL'i (PUBLIC, direkt .jpg/.png - redirect yok!)
        caption: Post caption'ı

    Returns:
        {"success": True, "id": "..."} veya {"success": False, "error": "..."}
    """
    print(f"[INSTAGRAM] Fotoğraf paylaşılıyor...")
    print(f"[INSTAGRAM] Image URL: {image_url[:80]}...")

    # Adım 1: Container oluştur
    container_id = await create_media_container(
        image_url=image_url,
        caption=caption,
        media_type="IMAGE"
    )

    if not container_id:
        return {"success": False, "error": "Media container oluşturulamadı"}

    # Biraz bekle
    await asyncio.sleep(2)

    # Adım 2: Yayınla
    result = await publish_media(container_id)
    if result.get("success"):
        result["platform"] = "instagram"
    return result


async def post_video_to_instagram(
    video_url: str,
    caption: str = ""
) -> Dict[str, Any]:
    """
    Instagram'a Reels paylaş

    Args:
        video_url: Video URL'i (PUBLIC erişilebilir!)
        caption: Reels caption'ı

    Returns:
        {"success": True, "id": "..."} veya {"success": False, "error": "..."}
    """
    print(f"[INSTAGRAM] Reels paylaşılıyor...")

    # Adım 1: REELS container oluştur
    container_id = await create_media_container(
        video_url=video_url,
        caption=caption,
        media_type="REELS"
    )

    if not container_id:
        return {"success": False, "error": "Media container oluşturulamadı"}

    # Video processing bekle
    print("[INSTAGRAM] Video işleniyor, bekleyin...")
    max_attempts = 30
    for attempt in range(max_attempts):
        await asyncio.sleep(10)

        status = await check_container_status(container_id)
        status_code = status.get("status_code")

        if status_code == "FINISHED":
            print("[INSTAGRAM] Video işleme tamamlandı!")
            break
        elif status_code == "ERROR":
            error_msg = status.get("status", "Unknown error")
            return {"success": False, "error": f"Video processing error: {error_msg}"}
        elif status_code == "IN_PROGRESS":
            print(f"[INSTAGRAM] Video işleniyor... ({attempt + 1}/{max_attempts})")
        else:
            print(f"[INSTAGRAM] Status: {status_code}")
    else:
        return {"success": False, "error": "Video processing timeout"}

    # Adım 2: Yayınla
    result = await publish_media(container_id)
    if result.get("success"):
        result["platform"] = "instagram_reels"
    return result


async def post_carousel_to_instagram(
    image_urls: List[str],
    caption: str = ""
) -> Dict[str, Any]:
    """
    Instagram'a Carousel (çoklu görsel) paylaş

    Args:
        image_urls: Görsel URL listesi (2-10 arası, PUBLIC!)
        caption: Post caption'ı

    Returns:
        {"success": True, "id": "..."} veya {"success": False, "error": "..."}
    """
    if len(image_urls) < 2 or len(image_urls) > 10:
        return {"success": False, "error": "Carousel 2-10 arası görsel içermeli"}

    print(f"[INSTAGRAM] Carousel paylaşılıyor ({len(image_urls)} görsel)...")

    # Adım 1: Her görsel için child container oluştur (retry ile)
    MAX_RETRIES = 3
    RETRY_DELAY = 3  # saniye (exponential: 3, 6, 9)

    children_ids = []
    for i, image_url in enumerate(image_urls):
        print(f"[INSTAGRAM] Carousel item {i+1}/{len(image_urls)} oluşturuluyor...")

        container_id = None
        for attempt in range(MAX_RETRIES):
            container_id = await create_media_container(
                image_url=image_url,
                media_type="IMAGE",
                is_carousel_item=True
            )

            if container_id:
                break  # Başarılı

            # Retry gerekli
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (attempt + 1)
                print(f"[INSTAGRAM] Item {i+1} retry {attempt + 1}/{MAX_RETRIES}, {wait_time}s bekleniyor...")
                await asyncio.sleep(wait_time)

        if container_id:
            children_ids.append(container_id)
            await asyncio.sleep(2)  # Rate limit
        else:
            print(f"[INSTAGRAM] Item {i+1} {MAX_RETRIES} denemede de oluşturulamadı!")

    if len(children_ids) < 2:
        return {"success": False, "error": "En az 2 carousel item gerekli"}

    # Adım 2: Ana carousel container oluştur
    carousel_container_id = await create_carousel_container(
        children_ids=children_ids,
        caption=caption
    )

    if not carousel_container_id:
        return {"success": False, "error": "Carousel container oluşturulamadı"}

    # Biraz bekle
    await asyncio.sleep(3)

    # Adım 3: Yayınla
    result = await publish_media(carousel_container_id)
    if result.get("success"):
        result["platform"] = "instagram_carousel"
        result["slide_count"] = len(children_ids)
    return result


async def upload_image_to_cdn(local_path: str) -> Optional[str]:
    """
    Lokal görseli CDN'e yükle ve public URL döndür

    Args:
        local_path: Lokal dosya yolu

    Returns:
        Public URL veya None
    """
    imgbb_key = os.getenv("IMGBB_API_KEY")

    if imgbb_key and os.path.exists(local_path):
        try:
            import base64

            with open(local_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.imgbb.com/1/upload",
                    data={
                        "key": imgbb_key,
                        "image": image_data
                    }
                ) as response:
                    result = await response.json()

                    if result.get("success"):
                        url = result["data"]["url"]
                        print(f"[INSTAGRAM] Görsel yüklendi: {url}")
                        return url
                    else:
                        print(f"[INSTAGRAM] Imgbb error: {result}")

        except Exception as e:
            print(f"[INSTAGRAM] CDN upload error: {e}")

    return None


async def post_reels_to_instagram(
    video_path: str,
    caption: str = "",
    max_retries: int = 3,
    skip_conversion: bool = False
) -> Dict[str, Any]:
    """
    Lokal video dosyasını Instagram Reels olarak paylaş

    Args:
        video_path: Lokal video dosyası yolu
        caption: Reels caption'ı
        max_retries: Maksimum deneme sayısı
        skip_conversion: Video dönüşümünü atla

    Returns:
        {"success": True, "id": "...", "cdn_url": "..."} veya hata
    """
    if not os.path.exists(video_path):
        return {"success": False, "error": f"Video dosyası bulunamadı: {video_path}"}

    print(f"[INSTAGRAM REELS] Reels paylaşılıyor...")
    print(f"[INSTAGRAM REELS] Video: {video_path}")

    # Video'yu Instagram formatına dönüştür
    upload_path = video_path
    if not skip_conversion:
        print("[INSTAGRAM REELS] Video Instagram formatına dönüştürülüyor...")
        convert_result = await convert_video_for_instagram(video_path)

        if not convert_result.get("success"):
            print(f"[INSTAGRAM REELS] Dönüşüm hatası: {convert_result.get('error')}")
            print("[INSTAGRAM REELS] Orijinal video ile devam ediliyor...")
        else:
            upload_path = convert_result.get("output_path", video_path)
            if convert_result.get("converted"):
                print(f"[INSTAGRAM REELS] Dönüştürüldü: {upload_path}")

    # Video'yu Cloudinary'ye yükle
    try:
        from app.cloudinary_helper import upload_video_to_cloudinary

        cdn_result = await upload_video_to_cloudinary(upload_path)

        if not cdn_result.get("success"):
            return {"success": False, "error": f"CDN upload failed: {cdn_result.get('error')}"}

        video_url = cdn_result.get("url")
        print(f"[INSTAGRAM REELS] CDN URL: {video_url}")

    except ImportError:
        return {"success": False, "error": "cloudinary_helper not available"}
    except Exception as e:
        return {"success": False, "error": f"CDN error: {str(e)}"}

    # Instagram Reels olarak paylaş
    for attempt in range(max_retries):
        try:
            print(f"[INSTAGRAM REELS] Deneme {attempt + 1}/{max_retries}")

            result = await post_video_to_instagram(
                video_url=video_url,
                caption=caption
            )

            if result.get("success"):
                result["cdn_url"] = video_url
                print(f"[INSTAGRAM REELS] Başarıyla yayınlandı! ID: {result.get('id')}")
                return result

            error = result.get("error", "Unknown error")
            print(f"[INSTAGRAM REELS] Hata: {error}")

            if attempt < max_retries - 1:
                print(f"[INSTAGRAM REELS] 15 saniye sonra tekrar deneniyor...")
                await asyncio.sleep(15)

        except Exception as e:
            print(f"[INSTAGRAM REELS] Exception: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(10)

    return {"success": False, "error": "Max retries exceeded", "cdn_url": video_url}


async def get_media_insights(media_id: str) -> Dict[str, Any]:
    """
    Post insights al

    Args:
        media_id: Instagram post ID

    Returns:
        Insights dictionary
    """
    creds = get_instagram_credentials()

    url = f"{GRAPH_API_URL}/{media_id}/insights"
    params = {
        "metric": "impressions,reach,engagement,saved",
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

                if "error" in data:
                    return {"success": False, "error": data["error"].get("message")}

                # Parse insights
                insights = {}
                for item in data.get("data", []):
                    insights[item["name"]] = item["values"][0]["value"]

                return {"success": True, "insights": insights}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_recent_media(limit: int = 10) -> Dict[str, Any]:
    """
    Son paylaşılan medyaları al

    Args:
        limit: Kaç post alınacak

    Returns:
        Media listesi
    """
    creds = get_instagram_credentials()

    url = f"{GRAPH_API_URL}/{creds['user_id']}/media"
    params = {
        "fields": "id,caption,timestamp,media_type,like_count,comments_count",
        "limit": limit,
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

                if "error" in data:
                    return {"success": False, "error": data["error"].get("message")}

                return {"success": True, "media": data.get("data", [])}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def test_instagram_connection():
    """Instagram bağlantısını test et"""
    print("\n=== Instagram API Bağlantı Testi ===\n")
    print(f"Endpoint: {GRAPH_API_URL}\n")

    creds = get_instagram_credentials()

    if not creds["access_token"]:
        print("[FAIL] INSTAGRAM_ACCESS_TOKEN tanımlı değil!")
        return False

    if not creds["user_id"]:
        print("[FAIL] INSTAGRAM_USER_ID tanımlı değil!")
        return False

    # Hesap bilgisi al
    result = await get_account_info()

    if result.get("success"):
        print(f"\n[OK] Instagram bağlantısı başarılı!")
        print(f"[OK] Username: @{result.get('username')}")
        print(f"[OK] User ID: {result.get('id')}")
        print(f"[OK] Followers: {result.get('followers_count', 0)}")
        print(f"[OK] Posts: {result.get('media_count', 0)}")
        return True
    else:
        print(f"\n[FAIL] Instagram bağlantısı başarısız!")
        print(f"[ERROR] {result.get('error')}")
        print("\n[INFO] Kontrol edilecekler:")
        print("  1. INSTAGRAM_ACCESS_TOKEN .env'de tanımlı mı?")
        print("  2. INSTAGRAM_USER_ID .env'de tanımlı mı?")
        print("  3. Access token geçerli mi?")
        return False


if __name__ == "__main__":
    asyncio.run(test_instagram_connection())
