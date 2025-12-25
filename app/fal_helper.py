"""
fal.ai Video Generation Helper - Kling AI entegrasyonu

Text-to-video veya image-to-video destekli.
"""
import os
import logging
import httpx
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

# FAL API key
FAL_API_KEY = settings.fal_api_key or os.getenv("FAL_API_KEY", "")


class FalVideoGenerator:
    """fal.ai uzerinden Kling AI video uretimi."""

    # Model endpoint mappings
    # text-to-video: v2.5-turbo (standard/pro), v2.1 (master)
    # image-to-video: v2.1 (tüm modeller)
    MODELS = {
        "kling_standard": {
            "text_to_video": "fal-ai/kling-video/v2.5-turbo/standard/text-to-video",
            "image_to_video": "fal-ai/kling-video/v2.1/standard/image-to-video",
            "name": "Kling 2.5 Turbo Standard",
            "max_duration": 10
        },
        "kling_pro": {
            "text_to_video": "fal-ai/kling-video/v2.5-turbo/pro/text-to-video",
            "image_to_video": "fal-ai/kling-video/v2.1/pro/image-to-video",
            "name": "Kling 2.5 Turbo Pro",
            "max_duration": 10
        },
        "kling_master": {
            "text_to_video": "fal-ai/kling-video/v2.1/master/text-to-video",
            "image_to_video": "fal-ai/kling-video/v2.1/master/image-to-video",
            "name": "Kling 2.1 Master",
            "max_duration": 10
        },
        "kling_26_pro": {
            "text_to_video": "fal-ai/kling-video/v2.6/pro/text-to-video",
            "image_to_video": "fal-ai/kling-video/v2.6/pro/image-to-video",
            "name": "Kling 2.6 Pro",
            "max_duration": 10,
            "has_audio": True
        },
        # Minimax Hailuo 02 modelleri
        "hailuo_standard": {
            "text_to_video": "fal-ai/minimax/hailuo-2.3/standard/text-to-video",
            "name": "Hailuo 02 Standard",
            "max_duration": 6
        },
        "hailuo_pro": {
            "text_to_video": "fal-ai/minimax/hailuo-2.3/pro/text-to-video",
            "name": "Hailuo 02 Pro",
            "max_duration": 6
        },
        # Wan 2.6
        "wan_26": {
            "text_to_video": "wan/v2.6/text-to-video",
            "name": "Wan 2.6",
            "max_duration": 15
        }
    }

    # FAL API base URL
    BASE_URL = "https://queue.fal.run"

    @staticmethod
    async def generate_video(
        prompt: str,
        model: str = "kling_pro",
        duration: int = 5,
        aspect_ratio: str = "9:16",
        image_url: Optional[str] = None,
        generate_audio: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        fal.ai uzerinden Kling AI ile video uret.

        Args:
            prompt: Video icerigi icin metin aciklamasi
            model: kling_standard, kling_pro, kling_master, kling_26_pro, hailuo_standard, hailuo_pro veya wan_26
            duration: Video suresi (5 veya 10 saniye)
            aspect_ratio: Video orani ("9:16" dikey, "16:9" yatay, "1:1" kare)
            image_url: Opsiyonel - image-to-video icin kaynak gorsel URL
            generate_audio: Opsiyonel - Kling 2.6+ icin ambient ses uretimi (varsayilan True)

        Returns:
            {
                "success": bool,
                "video_url": str,  # CDN video URL
                "video_path": str,  # Lokal dosya yolu (indirildiyse)
                "duration": int,
                "model": str,
                "provider": str
            }
        """
        if not FAL_API_KEY:
            raise ValueError("FAL_API_KEY tanımli degil! .env dosyasina FAL_API_KEY ekleyin.")

        model_config = FalVideoGenerator.MODELS.get(model)
        if not model_config:
            raise ValueError(f"Gecersiz model: {model}. Kullanilabilir: {list(FalVideoGenerator.MODELS.keys())}")

        # Duration kontrolu
        duration = min(duration, model_config["max_duration"])

        # Endpoint secimi (text-to-video veya image-to-video)
        if image_url:
            endpoint = model_config["image_to_video"]
            request_body = {
                "prompt": prompt,
                "image_url": image_url,
                "duration": str(duration),
                "aspect_ratio": aspect_ratio,
                "negative_prompt": "blur, distort, low quality, static, frozen, text, watermark"
            }
        else:
            endpoint = model_config["text_to_video"]
            request_body = {
                "prompt": prompt,
                "duration": str(duration),
                "aspect_ratio": aspect_ratio,
                "negative_prompt": "blur, distort, low quality, static, frozen, text, watermark"
            }

        # Audio desteği (Kling 2.6+)
        if model_config.get("has_audio"):
            if generate_audio is None:
                generate_audio = True  # 2.6 için varsayılan açık
            request_body["generate_audio"] = generate_audio

        logger.info(f"fal.ai video uretimi basliyor: {model_config['name']}, {duration}s, {aspect_ratio}")

        try:
            # Queue request gonder
            result = await FalVideoGenerator._submit_and_poll(endpoint, request_body)

            video_url = result.get("video", {}).get("url")
            if not video_url:
                raise Exception(f"Video URL alinamadi: {result}")

            # Video'yu lokal olarak indir
            video_path = await FalVideoGenerator._download_video(video_url)

            logger.info(f"Video uretildi: {video_path}")

            return {
                "success": True,
                "video_url": video_url,
                "video_path": video_path,
                "duration": duration,
                "model": model_config["name"],
                "model_used": f"kling-{model.replace('kling_', '')}",
                "provider": "fal.ai/kling",
                "has_audio": model_config.get("has_audio", False)
            }

        except Exception as e:
            logger.error(f"fal.ai video uretim hatasi: {e}")
            return {
                "success": False,
                "error": str(e),
                "model": model_config["name"],
                "provider": "fal.ai/kling"
            }

    @staticmethod
    async def _submit_and_poll(endpoint: str, request_body: Dict) -> Dict:
        """
        fal.ai queue API ile request gonder ve sonucu bekle.
        """
        headers = {
            "Authorization": f"Key {FAL_API_KEY}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=600.0) as client:
            # Submit request
            submit_url = f"{FalVideoGenerator.BASE_URL}/{endpoint}"
            logger.debug(f"Submitting to: {submit_url}")

            response = await client.post(submit_url, json=request_body, headers=headers)
            response.raise_for_status()

            result = response.json()

            # Eger sonuc hemen geldiyse (sync response)
            if "video" in result:
                return result

            # Queue response - poll for result
            request_id = result.get("request_id")
            if not request_id:
                raise Exception(f"Request ID alinamadi: {result}")

            logger.info(f"Video kuyrukta: {request_id}")

            # fal.ai response'tan URL'leri al (dinamik format)
            status_url = result.get("status_url")
            result_url = result.get("response_url")

            if not status_url or not result_url:
                # Fallback: eski format (base model path kullan)
                base_model = endpoint.split("/text-to-video")[0].split("/image-to-video")[0]
                status_url = f"https://queue.fal.run/{base_model}/requests/{request_id}/status"
                result_url = f"https://queue.fal.run/{base_model}/requests/{request_id}"

            logger.debug(f"Status URL: {status_url}")
            logger.debug(f"Result URL: {result_url}")

            max_attempts = 120  # 10 dakika (5 saniye aralikli)
            for attempt in range(max_attempts):
                await asyncio.sleep(5)

                # Check status
                status_response = await client.get(status_url, headers=headers)
                status_response.raise_for_status()
                status = status_response.json()

                current_status = status.get("status", "unknown")
                logger.debug(f"Video durumu [{attempt+1}/{max_attempts}]: {current_status}")

                if current_status == "COMPLETED":
                    # Get result
                    result_response = await client.get(result_url, headers=headers)
                    result_response.raise_for_status()
                    return result_response.json()

                elif current_status in ["FAILED", "CANCELLED"]:
                    error_msg = status.get("error", "Bilinmeyen hata")
                    raise Exception(f"Video uretimi basarisiz: {error_msg}")

                # IN_QUEUE veya IN_PROGRESS - devam et

            raise Exception("Video uretimi zaman asimina ugradi (10 dakika)")

    @staticmethod
    async def _download_video(video_url: str) -> str:
        """
        Video'yu CDN'den indirip lokal dosyaya kaydet.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = settings.outputs_dir / f"kling_{timestamp}.mp4"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(video_url)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Video indirildi: {output_path} ({file_size_mb:.2f} MB)")

        return str(output_path)


# Convenience function
async def generate_kling_video(
    prompt: str,
    model: str = "kling_pro",
    duration: int = 5,
    aspect_ratio: str = "9:16"
) -> Dict[str, Any]:
    """
    Kling AI ile video uret (kolaylik fonksiyonu).

    Args:
        prompt: Video prompt'u
        model: kling_standard, kling_pro, kling_master
        duration: 5 veya 10 saniye
        aspect_ratio: 9:16 (dikey), 16:9 (yatay), 1:1 (kare)

    Returns:
        Video sonucu dict
    """
    return await FalVideoGenerator.generate_video(
        prompt=prompt,
        model=model,
        duration=duration,
        aspect_ratio=aspect_ratio
    )
