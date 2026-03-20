"""
Kling AI Direct API Helper - Text-to-Video Generation
Kuaishou Kling 3.0 Pro via direct API (replaces fal.ai middleman)

Base URL: https://api-singapore.klingai.com
Auth: JWT (HS256) with access_key/secret_key
"""
import os
import time
import logging
import httpx
import asyncio
import uuid
import jwt
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class KlingHelper:
    """Direct Kling AI API integration for video generation."""

    BASE_URL = "https://api-singapore.klingai.com"

    # TODO: multi_prompt support for multi-shot (up to 6 shots, 3-15s)

    def __init__(self):
        self.access_key = settings.kling_access_key or os.getenv("KLING_ACCESS_KEY", "")
        self.secret_key = settings.kling_secret_key or os.getenv("KLING_SECRET_KEY", "")
        self._token: Optional[str] = None
        self._token_expires: float = 0

    def _generate_jwt(self) -> str:
        """Generate JWT token with auto-renewal (30 min expiry, renew at 5 min remaining)."""
        now = time.time()

        # Return cached token if still valid (> 5 min remaining)
        if self._token and (self._token_expires - now) > 300:
            return self._token

        if not self.access_key or not self.secret_key:
            raise ValueError(
                "KLING_ACCESS_KEY ve KLING_SECRET_KEY tanimli degil! "
                ".env dosyasina ekleyin."
            )

        headers = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": self.access_key,
            "exp": int(now) + 1800,  # 30 min
            "nbf": int(now) - 5,
        }

        self._token = jwt.encode(payload, self.secret_key, algorithm="HS256", headers=headers)
        self._token_expires = now + 1800
        logger.debug("JWT token generated, expires in 30 min")
        return self._token

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
        Generate video via Kling Direct API.

        Args:
            prompt: Video description (max 2500 chars)
            duration: 5 or 10 seconds
            aspect_ratio: "9:16", "16:9", or "1:1"
            model_name: "kling-v3" (Kling 3.0)
            mode: "pro" or "std"
            negative_prompt: What to avoid
            cfg_scale: Guidance scale (0-1)
            generate_audio: Ignored for direct API (kept for interface compat)

        Returns:
            {"success": bool, "video_url": str, "video_path": str, "duration": int, ...}
        """
        logger.info(f"Kling Direct API video uretimi: {model_name}/{mode}, {duration}s, {aspect_ratio}")

        try:
            token = self._generate_jwt()

            request_body = {
                "prompt": prompt[:2500],
                "negative_prompt": negative_prompt[:2500],
                "model_name": model_name,
                "duration": str(duration),
                "aspect_ratio": aspect_ratio,
                "mode": mode,
                "cfg_scale": cfg_scale,
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Submit task
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/v1/videos/text2video",
                    json=request_body,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

            task_id = result.get("data", {}).get("task_id")
            if not task_id:
                raise Exception(f"Task ID alinamadi: {result}")

            logger.info(f"Kling task olusturuldu: {task_id}")

            # Poll until complete
            task_result = await self._poll_task(task_id)

            # Extract video URL from result
            works = task_result.get("data", {}).get("task_result", {}).get("videos", [])
            if not works:
                raise Exception(f"Video URL alinamadi: {task_result}")

            video_url = works[0].get("url")
            if not video_url:
                raise Exception(f"Video URL bos: {works[0]}")

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
                "provider": "Kling Direct API",
                "has_audio": True,
            }

        except Exception as e:
            logger.error(f"Kling Direct API hatasi: {e}")
            return {
                "success": False,
                "error": str(e),
                "model": "Kling 3.0 Pro",
                "provider": "Kling Direct API",
            }

    async def _poll_task(self, task_id: str, timeout: int = 300, interval: int = 10) -> dict:
        """
        Poll task status until complete.

        Args:
            task_id: Task ID from creation response
            timeout: Max wait in seconds (default 5 min)
            interval: Poll interval in seconds (default 10s)
        """
        token = self._generate_jwt()
        headers = {"Authorization": f"Bearer {token}"}

        max_attempts = timeout // interval
        start_time = time.time()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(max_attempts):
                await asyncio.sleep(interval)

                # Refresh token if needed
                headers["Authorization"] = f"Bearer {self._generate_jwt()}"

                response = await client.get(
                    f"{self.BASE_URL}/v1/videos/{task_id}",
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

                status = result.get("data", {}).get("task_status", "unknown")
                elapsed = int(time.time() - start_time)
                logger.debug(f"Kling task [{attempt+1}/{max_attempts}]: {status} ({elapsed}s)")

                if status == "succeed":
                    return result
                elif status in ("failed", "cancelled"):
                    error_msg = result.get("data", {}).get("task_status_msg", "Bilinmeyen hata")
                    raise Exception(f"Video uretimi basarisiz: {error_msg}")
                # processing, submitted, staged — continue polling

        raise Exception(f"Video uretimi zaman asimina ugradi ({timeout}s)")

    async def _download_video(self, video_url: str) -> str:
        """Download video from Kling CDN to local file."""
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
        """Test API connection with JWT auth (no video generation)."""
        try:
            token = self._generate_jwt()
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/v1/videos/text2video",
                    headers={"Authorization": f"Bearer {token}"},
                )
            return {
                "success": True,
                "status_code": response.status_code,
                "jwt_ok": True,
                "message": f"API reachable (HTTP {response.status_code})",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "jwt_ok": self._token is not None,
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
