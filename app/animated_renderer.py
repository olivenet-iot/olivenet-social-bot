"""
Olivenet Social Media Bot - Animated Renderer
Converts HTML with CSS animations to MP4/GIF using Playwright and ffmpeg.
"""
import asyncio
import os
import shutil
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


async def render_animated_html_to_video(
    html_content: str,
    output_path: str,
    duration: int = 4,
    fps: int = 30
) -> str:
    """
    Convert animated HTML to MP4 video.

    Args:
        html_content: CSS animated HTML content
        output_path: Output video file path (.mp4)
        duration: Video duration in seconds
        fps: Frames per second

    Returns:
        Output video file path
    """
    from playwright.async_api import async_playwright

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    frames_dir = f"/tmp/frames_{timestamp}"
    os.makedirs(frames_dir, exist_ok=True)

    total_frames = duration * fps
    frame_delay_ms = int(1000 / fps)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={'width': 1080, 'height': 1080})

            await page.set_content(html_content, wait_until='domcontentloaded')

            # Wait a bit for initial animations to start
            await page.wait_for_timeout(100)

            logger.info(f"Rendering {total_frames} frames at {fps} FPS...")

            for frame in range(total_frames):
                frame_path = os.path.join(frames_dir, f"frame_{frame:04d}.png")
                await page.screenshot(path=frame_path, type='png')
                await page.wait_for_timeout(frame_delay_ms)

                # Progress logging every 30 frames
                if frame % 30 == 0:
                    progress = int(frame / total_frames * 100)
                    logger.info(f"Frame {frame}/{total_frames} ({progress}%)")

            await browser.close()

        # Use ffmpeg to create video
        ffmpeg_cmd = (
            f"ffmpeg -y -framerate {fps} -i {frames_dir}/frame_%04d.png "
            f"-c:v libx264 -pix_fmt yuv420p -crf 23 "
            f"-vf 'scale=1080:1080' {output_path} 2>/dev/null"
        )

        process = await asyncio.create_subprocess_shell(
            ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"ffmpeg error: {stderr.decode()}")
            raise Exception(f"ffmpeg failed: {stderr.decode()[:200]}")

        logger.info(f"Video created: {output_path}")
        return output_path

    finally:
        # Cleanup temp frames
        if os.path.exists(frames_dir):
            shutil.rmtree(frames_dir)


async def render_animated_html_to_gif(
    html_content: str,
    output_path: str,
    duration: int = 3,
    fps: int = 15
) -> str:
    """
    Convert animated HTML to GIF.

    Args:
        html_content: CSS animated HTML content
        output_path: Output GIF file path (.gif)
        duration: Duration in seconds
        fps: Frames per second (lower for smaller file size)

    Returns:
        Output GIF file path
    """
    from playwright.async_api import async_playwright

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    frames_dir = f"/tmp/frames_{timestamp}"
    os.makedirs(frames_dir, exist_ok=True)

    total_frames = duration * fps
    frame_delay_ms = int(1000 / fps)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={'width': 1080, 'height': 1080})

            await page.set_content(html_content, wait_until='domcontentloaded')
            await page.wait_for_timeout(100)

            logger.info(f"Rendering {total_frames} GIF frames at {fps} FPS...")

            for frame in range(total_frames):
                frame_path = os.path.join(frames_dir, f"frame_{frame:04d}.png")
                await page.screenshot(path=frame_path, type='png')
                await page.wait_for_timeout(frame_delay_ms)

            await browser.close()

        # Use ffmpeg to create optimized GIF
        ffmpeg_cmd = (
            f"ffmpeg -y -framerate {fps} -i {frames_dir}/frame_%04d.png "
            f"-vf 'fps={fps},scale=540:540:flags=lanczos,split[s0][s1];"
            f"[s0]palettegen[p];[s1][p]paletteuse' "
            f"{output_path} 2>/dev/null"
        )

        process = await asyncio.create_subprocess_shell(
            ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"ffmpeg GIF error: {stderr.decode()}")
            raise Exception(f"ffmpeg failed: {stderr.decode()[:200]}")

        logger.info(f"GIF created: {output_path}")
        return output_path

    finally:
        if os.path.exists(frames_dir):
            shutil.rmtree(frames_dir)


async def render_quick_preview(
    html_content: str,
    output_path: str
) -> str:
    """
    Quick preview - renders only first frame as static image.
    Useful for testing HTML before full video render.

    Args:
        html_content: HTML content
        output_path: Output PNG file path

    Returns:
        Output image path
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1080, 'height': 1080})

        await page.set_content(html_content, wait_until='domcontentloaded')
        await page.wait_for_timeout(500)  # Wait for animations to start

        await page.screenshot(path=output_path, type='png')
        await browser.close()

    return output_path
