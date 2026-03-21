"""
Kling AI Video Helper - Text-to-Video Generation via fal.ai
Kuaishou Kling 3.0 Pro via fal.ai queue API (pay-as-you-go)

Endpoint: fal-ai/kling-video/v3/pro/text-to-video
Auth: Key {FAL_API_KEY}
"""
import os
import logging
import httpx
import asyncio
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

FAL_API_KEY = settings.fal_api_key or os.getenv("FAL_API_KEY", "")
FAL_BASE_URL = "https://queue.fal.run"
FAL_ENDPOINT = "fal-ai/kling-video/v3/pro/text-to-video"


class KlingHelper:
    """Kling AI video generation via fal.ai queue API."""

    def __init__(self):
        self.api_key = FAL_API_KEY

    async def generate_video(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "9:16",
        model_name: str = "kling-v3",
        mode: str = "pro",
        negative_prompt: str = "blur, distort, low quality, static, frozen, text, watermark",
        cfg_scale: float = 0.5,
        generate_audio: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Generate video via Kling 3.0 Pro on fal.ai.

        Args:
            prompt: Video description (max 2500 chars)
            duration: 5 or 10 seconds
            aspect_ratio: "9:16", "16:9", or "1:1"
            model_name: Kept for interface compat (encoded in fal.ai endpoint)
            mode: Kept for interface compat (encoded in fal.ai endpoint)
            negative_prompt: What to avoid
            cfg_scale: Guidance scale (0-1)
            generate_audio: True/False for native audio, None = fal.ai default (True)

        Returns:
            {"success": bool, "video_url": str, "video_path": str, "duration": int, ...}
        """
        logger.info(f"Kling fal.ai video uretimi: {duration}s, {aspect_ratio}")

        if not self.api_key:
            return {
                "success": False,
                "error": "FAL_API_KEY not configured",
                "model": "Kling 3.0 Pro",
                "provider": "fal.ai",
            }

        try:
            request_body = {
                "prompt": prompt[:2500],
                "duration": str(duration),
                "aspect_ratio": aspect_ratio,
                "negative_prompt": negative_prompt,
                "cfg_scale": cfg_scale,
            }

            if generate_audio is not None:
                request_body["generate_audio"] = generate_audio

            # Submit and poll fal.ai queue
            result = await self._submit_and_poll(request_body)

            # Extract video URL
            video_url = result.get("video", {}).get("url")
            if not video_url:
                raise Exception(f"Video URL alinamadi: {result}")

            # Download video locally
            video_path = await self._download_video(video_url)

            logger.info(f"Video uretildi: {video_path}")

            return {
                "success": True,
                "video_url": video_url,
                "video_path": video_path,
                "duration": duration,
                "model": "Kling 3.0 Pro",
                "model_used": "kling-v3_pro",
                "provider": "fal.ai",
                "has_audio": generate_audio is not False,
            }

        except Exception as e:
            logger.error(f"Kling fal.ai hatasi: {e}")
            return {
                "success": False,
                "error": str(e),
                "model": "Kling 3.0 Pro",
                "provider": "fal.ai",
            }

    async def _submit_and_poll(self, request_body: dict) -> dict:
        """
        Submit video generation to fal.ai queue and poll until complete.

        Timeout: 30 minutes (video generation can be slow)
        Poll interval: 5 seconds
        """
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=600.0) as client:
            # Submit request
            submit_url = f"{FAL_BASE_URL}/{FAL_ENDPOINT}"
            logger.debug(f"  Submitting to: {submit_url}")

            response = await client.post(submit_url, json=request_body, headers=headers)
            response.raise_for_status()

            result = response.json()

            # If result is ready immediately (sync response)
            if "video" in result:
                return result

            # Queue response - need to poll
            request_id = result.get("request_id")
            if not request_id:
                raise Exception(f"No request_id in response: {result}")

            logger.info(f"  Request queued: {request_id}")

            # Get polling URLs from response
            status_url = result.get("status_url")
            result_url = result.get("response_url")

            if not status_url or not result_url:
                # Fallback: construct URLs manually
                status_url = f"{FAL_BASE_URL}/{FAL_ENDPOINT}/requests/{request_id}/status"
                result_url = f"{FAL_BASE_URL}/{FAL_ENDPOINT}/requests/{request_id}"

            # Poll for result (30 minutes max, 5 second intervals)
            max_attempts = 360
            for attempt in range(max_attempts):
                await asyncio.sleep(5)

                status_response = await client.get(status_url, headers=headers)
                status_response.raise_for_status()
                status = status_response.json()

                current_status = status.get("status", "unknown")
                logger.debug(f"  Status [{attempt + 1}/{max_attempts}]: {current_status}")

                if current_status == "COMPLETED":
                    result_response = await client.get(result_url, headers=headers)
                    result_response.raise_for_status()
                    return result_response.json()

                elif current_status in ["FAILED", "CANCELLED"]:
                    error_msg = status.get("error", "Unknown error")
                    raise Exception(f"fal.ai video generation failed: {error_msg}")

                # IN_QUEUE or IN_PROGRESS - continue polling

        raise Exception("fal.ai video generation timed out (30 minutes)")

    async def _download_video(self, video_url: str) -> str:
        """Download video from fal.ai CDN to local file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_suffix = uuid.uuid4().hex[:6]
        output_path = settings.outputs_dir / f"kling_{timestamp}_{unique_suffix}.mp4"

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(video_url)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Video indirildi: {output_path} ({file_size_mb:.2f} MB)")

        return str(output_path)

    async def test_connection(self) -> Dict[str, Any]:
        """Test fal.ai API connection (lightweight auth check)."""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "FAL_API_KEY not configured",
                }

            headers = {
                "Authorization": f"Key {self.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                # Send a minimal request to verify auth
                response = await client.post(
                    f"{FAL_BASE_URL}/{FAL_ENDPOINT}",
                    json={"prompt": "test", "duration": "3"},
                    headers=headers,
                )

            # Any non-auth-error response means the key is valid
            if response.status_code in (200, 422):
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "message": f"fal.ai API reachable (HTTP {response.status_code})",
                }

            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Invalid FAL_API_KEY (401 Unauthorized)",
                }

            return {
                "success": True,
                "status_code": response.status_code,
                "message": f"fal.ai API reachable (HTTP {response.status_code})",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


# Convenience function
async def generate_kling_video(
    prompt: str,
    duration: int = 5,
    aspect_ratio: str = "9:16",
) -> Dict[str, Any]:
    """
    Kling AI ile video uret (kolaylik fonksiyonu).

    Args:
        prompt: Video prompt'u
        duration: 5 veya 10 saniye
        aspect_ratio: 9:16 (dikey), 16:9 (yatay), 1:1 (kare)
    """
    helper = KlingHelper()
    return await helper.generate_video(
        prompt=prompt,
        duration=duration,
        aspect_ratio=aspect_ratio,
    )


if __name__ == "__main__":
    import asyncio

    helper = KlingHelper()
    result = asyncio.run(helper.test_connection())
    print(result)
