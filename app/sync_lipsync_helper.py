"""
Sync Lipsync Helper - fal.ai Sync Lipsync V2 Pro Integration

Generates lip-synced video from audio and talking head video.
Uses active speaker detection for natural lip movements.
"""

import os
import asyncio
import httpx
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

# FAL API key
FAL_API_KEY = settings.fal_api_key or os.getenv("FAL_API_KEY", "")


class SyncLipsyncHelper:
    """fal.ai Sync Lipsync V2 Pro integration for lip-sync video generation."""

    MODEL_ENDPOINT = "fal-ai/sync-lipsync/v2/pro"
    BASE_URL = "https://queue.fal.run"

    @staticmethod
    async def generate_lipsync_video(
        video_url: str,
        audio_url: str,
        sync_mode: str = "cut_off"
    ) -> Dict[str, Any]:
        """
        Generate lip-synced video from audio and base video.

        Args:
            video_url: Public URL of base video (talking head, from Cloudinary)
            audio_url: Public URL of audio file (dialog TTS, from Cloudinary)
            sync_mode: How to handle duration mismatch
                - "cut_off": Cut longer content (default, recommended)
                - "loop": Loop shorter content
                - "bounce": Reverse and play shorter content
                - "silence": Add silence padding

        Returns:
            {
                "success": bool,
                "video_url": str,      # CDN URL of lip-synced video
                "video_path": str,     # Local file path (downloaded)
                "duration": float,     # Video duration in seconds
                "error": str           # Error message if failed
            }
        """
        if not FAL_API_KEY:
            return {
                "success": False,
                "error": "FAL_API_KEY not configured"
            }

        if not video_url or not audio_url:
            return {
                "success": False,
                "error": "Both video_url and audio_url are required"
            }

        request_body = {
            "video_url": video_url,
            "audio_url": audio_url,
            "sync_mode": sync_mode
        }

        logger.info(f"[LIPSYNC] Starting lip-sync generation with mode: {sync_mode}")
        logger.debug(f"[LIPSYNC] Video URL: {video_url[:80]}...")
        logger.debug(f"[LIPSYNC] Audio URL: {audio_url[:80]}...")

        try:
            # Submit and poll for result
            result = await SyncLipsyncHelper._submit_and_poll(
                SyncLipsyncHelper.MODEL_ENDPOINT,
                request_body
            )

            # Extract video URL from result
            video_result_url = result.get("video", {}).get("url")
            if not video_result_url:
                # Try alternate response structure
                video_result_url = result.get("video_url")

            if not video_result_url:
                return {
                    "success": False,
                    "error": f"No video URL in response: {result}"
                }

            # Download video to local path
            video_path = await SyncLipsyncHelper._download_video(video_result_url)

            logger.info(f"[LIPSYNC] Video generated successfully: {video_path}")

            return {
                "success": True,
                "video_url": video_result_url,
                "video_path": video_path,
                "duration": result.get("duration", 0),
                "provider": "fal.ai/sync-lipsync"
            }

        except Exception as e:
            logger.error(f"[LIPSYNC] Generation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    async def _submit_and_poll(endpoint: str, request_body: Dict) -> Dict:
        """
        Submit request to fal.ai queue API and poll for result.

        Timeout: 10 minutes (lip-sync processing takes longer than video generation)
        """
        headers = {
            "Authorization": f"Key {FAL_API_KEY}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=700.0) as client:
            # Submit request
            submit_url = f"{SyncLipsyncHelper.BASE_URL}/{endpoint}"
            logger.debug(f"[LIPSYNC] Submitting to: {submit_url}")

            response = await client.post(submit_url, json=request_body, headers=headers)
            response.raise_for_status()

            result = response.json()

            # If result is ready immediately (sync response)
            if "video" in result or "video_url" in result:
                return result

            # Queue response - need to poll for result
            request_id = result.get("request_id")
            if not request_id:
                raise Exception(f"No request_id in response: {result}")

            logger.info(f"[LIPSYNC] Request queued: {request_id}")

            # Get polling URLs from response (dynamic format)
            status_url = result.get("status_url")
            result_url = result.get("response_url")

            if not status_url or not result_url:
                # Fallback: construct URLs manually
                status_url = f"https://queue.fal.run/{endpoint}/requests/{request_id}/status"
                result_url = f"https://queue.fal.run/{endpoint}/requests/{request_id}"

            logger.debug(f"[LIPSYNC] Status URL: {status_url}")
            logger.debug(f"[LIPSYNC] Result URL: {result_url}")

            # Poll for result (10 minutes max, 5 second intervals)
            max_attempts = 120  # 10 minutes with 5 second intervals
            for attempt in range(max_attempts):
                await asyncio.sleep(5)

                # Check status
                status_response = await client.get(status_url, headers=headers)
                status_response.raise_for_status()
                status = status_response.json()

                current_status = status.get("status", "unknown")
                logger.debug(f"[LIPSYNC] Status [{attempt + 1}/{max_attempts}]: {current_status}")

                if current_status == "COMPLETED":
                    # Get result
                    result_response = await client.get(result_url, headers=headers)
                    result_response.raise_for_status()
                    return result_response.json()

                elif current_status in ["FAILED", "CANCELLED"]:
                    error_msg = status.get("error", "Unknown error")
                    raise Exception(f"Lip-sync failed: {error_msg}")

                # IN_QUEUE or IN_PROGRESS - continue polling

            raise Exception("Lip-sync generation timed out (10 minutes)")

    @staticmethod
    async def _download_video(video_url: str) -> str:
        """
        Download video from CDN to local file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_suffix = uuid.uuid4().hex[:6]
        output_path = settings.outputs_dir / f"lipsync_{timestamp}_{unique_suffix}.mp4"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(video_url)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"[LIPSYNC] Video downloaded: {output_path} ({file_size_mb:.2f} MB)")

        return str(output_path)


# Convenience function
async def apply_lipsync(
    video_url: str,
    audio_url: str,
    sync_mode: str = "cut_off"
) -> Dict[str, Any]:
    """
    Apply lip-sync to video using Sync Lipsync V2 Pro.

    Args:
        video_url: Public URL of talking head video
        audio_url: Public URL of dialog audio
        sync_mode: Duration mismatch handling (cut_off, loop, bounce, silence)

    Returns:
        Result dict with success, video_url, video_path
    """
    return await SyncLipsyncHelper.generate_lipsync_video(
        video_url=video_url,
        audio_url=audio_url,
        sync_mode=sync_mode
    )
