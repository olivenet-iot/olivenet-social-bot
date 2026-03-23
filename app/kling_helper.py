"""
Kling AI Video Helper - Text-to-Video & Image-to-Video via fal.ai
Kuaishou Kling 3.0 Pro/Standard via fal.ai queue API (pay-as-you-go)

Endpoints:
- Pro text-to-video: fal-ai/kling-video/v3/pro/text-to-video
- Standard text-to-video: fal-ai/kling-video/v3/standard/text-to-video
- Pro image-to-video: fal-ai/kling-video/v3/pro/image-to-video
- Standard image-to-video: fal-ai/kling-video/v3/standard/image-to-video
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

# Dynamic endpoint map: (mode, generation_type) -> fal.ai endpoint
KLING_ENDPOINTS = {
    ("pro", "t2v"): "fal-ai/kling-video/v3/pro/text-to-video",
    ("standard", "t2v"): "fal-ai/kling-video/v3/standard/text-to-video",
    ("pro", "i2v"): "fal-ai/kling-video/v3/pro/image-to-video",
    ("standard", "i2v"): "fal-ai/kling-video/v3/standard/image-to-video",
}

# Backward compatibility alias
FAL_ENDPOINT = KLING_ENDPOINTS[("pro", "t2v")]


class KlingHelper:
    """Kling AI video generation via fal.ai queue API."""

    def __init__(self):
        self.api_key = FAL_API_KEY

    def _resolve_endpoint(self, mode: str = "pro", gen_type: str = "t2v") -> str:
        """Resolve fal.ai endpoint from mode and generation type."""
        key = (mode, gen_type)
        endpoint = KLING_ENDPOINTS.get(key)
        if not endpoint:
            logger.warning(f"Unknown Kling endpoint key {key}, falling back to pro t2v")
            endpoint = KLING_ENDPOINTS[("pro", "t2v")]
        return endpoint

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
        Generate video via Kling 3.0 on fal.ai.

        Args:
            prompt: Video description (max 2500 chars)
            duration: 5, 10, or 15 seconds (15 only for pro)
            aspect_ratio: "9:16", "16:9", or "1:1"
            model_name: Kept for interface compat
            mode: "pro" or "standard"
            negative_prompt: What to avoid
            cfg_scale: Guidance scale (0-1)
            generate_audio: True/False for native audio, None = fal.ai default (True)

        Returns:
            {"success": bool, "video_url": str, "video_path": str, "duration": int, ...}
        """
        model_label = "Kling 3.0 Pro" if mode == "pro" else "Kling 3.0 Standard"
        model_used = f"kling-v3_{mode}"

        logger.info(f"Kling fal.ai video uretimi ({mode}): {duration}s, {aspect_ratio}")

        if not self.api_key:
            return {
                "success": False,
                "error": "FAL_API_KEY not configured",
                "model": model_label,
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

            endpoint = self._resolve_endpoint(mode, "t2v")
            result = await self._submit_and_poll(request_body, endpoint=endpoint)

            # Extract video URL
            video_url = result.get("video", {}).get("url")
            if not video_url:
                raise Exception(f"Video URL alinamadi: {result}")

            # Download video locally
            video_path = await self._download_video(video_url)

            logger.info(f"Video uretildi ({mode}): {video_path}")

            return {
                "success": True,
                "video_url": video_url,
                "video_path": video_path,
                "duration": duration,
                "model": model_label,
                "model_used": model_used,
                "provider": "fal.ai",
                "has_audio": generate_audio is not False,
            }

        except Exception as e:
            logger.error(f"Kling fal.ai hatasi ({mode}): {e}")
            return {
                "success": False,
                "error": str(e),
                "model": model_label,
                "provider": "fal.ai",
            }

    async def generate_video_from_image(
        self,
        image_url: str,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "9:16",
        mode: str = "pro",
        negative_prompt: str = "blur, distort, low quality, static, frozen, text, watermark",
        cfg_scale: float = 0.5,
        generate_audio: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Generate video from a reference image using Kling i2v.

        Args:
            image_url: Public URL of the reference image
            prompt: Animation/motion description (max 2500 chars)
            duration: 5 or 10 seconds
            aspect_ratio: "9:16", "16:9", or "1:1"
            mode: "pro" or "standard"
            negative_prompt: What to avoid
            cfg_scale: Guidance scale (0-1)
            generate_audio: True/False for native audio

        Returns:
            {"success": bool, "video_url": str, "video_path": str, ...}
        """
        model_label = "Kling 3.0 Pro i2v" if mode == "pro" else "Kling 3.0 Standard i2v"
        model_used = f"kling-v3_{mode}_i2v"

        logger.info(f"Kling fal.ai i2v uretimi ({mode}): {duration}s, {aspect_ratio}")

        if not self.api_key:
            return {
                "success": False,
                "error": "FAL_API_KEY not configured",
                "model": model_label,
                "provider": "fal.ai",
            }

        try:
            request_body = {
                "prompt": prompt[:2500],
                "image_url": image_url,
                "duration": str(duration),
                "aspect_ratio": aspect_ratio,
                "negative_prompt": negative_prompt,
                "cfg_scale": cfg_scale,
            }

            if generate_audio is not None:
                request_body["generate_audio"] = generate_audio

            endpoint = self._resolve_endpoint(mode, "i2v")
            result = await self._submit_and_poll(request_body, endpoint=endpoint)

            # Extract video URL
            video_url = result.get("video", {}).get("url")
            if not video_url:
                raise Exception(f"Video URL alinamadi (i2v): {result}")

            # Download video locally
            video_path = await self._download_video(video_url)

            logger.info(f"i2v video uretildi ({mode}): {video_path}")

            return {
                "success": True,
                "video_url": video_url,
                "video_path": video_path,
                "duration": duration,
                "model": model_label,
                "model_used": model_used,
                "generation_type": "i2v",
                "provider": "fal.ai",
                "has_audio": generate_audio is not False,
            }

        except Exception as e:
            logger.error(f"Kling fal.ai i2v hatasi ({mode}): {e}")
            return {
                "success": False,
                "error": str(e),
                "model": model_label,
                "provider": "fal.ai",
            }

    async def _submit_and_poll(self, request_body: dict, endpoint: str = None) -> dict:
        """
        Submit video generation to fal.ai queue and poll until complete.

        Timeout: 30 minutes (video generation can be slow)
        Poll interval: 5 seconds
        """
        endpoint = endpoint or FAL_ENDPOINT

        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=600.0) as client:
            # Submit request
            submit_url = f"{FAL_BASE_URL}/{endpoint}"
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
                status_url = f"{FAL_BASE_URL}/{endpoint}/requests/{request_id}/status"
                result_url = f"{FAL_BASE_URL}/{endpoint}/requests/{request_id}"

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


if __name__ == "__main__":
    import asyncio

    helper = KlingHelper()
    result = asyncio.run(helper.test_connection())
    print(result)
