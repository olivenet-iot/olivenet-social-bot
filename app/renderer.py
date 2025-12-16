"""
Olivenet Social Media Bot - HTML to PNG Renderer
Uses Playwright for high-quality rendering.
"""
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page

from .config import settings

logger = logging.getLogger(__name__)

# Global browser instance for reuse
_browser: Optional[Browser] = None


async def get_browser() -> Browser:
    """Get or create a browser instance."""
    global _browser
    if _browser is None or not _browser.is_connected():
        playwright = await async_playwright().start()
        _browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        logger.info("Browser instance created")
    return _browser


async def close_browser():
    """Close the browser instance."""
    global _browser
    if _browser is not None:
        await _browser.close()
        _browser = None
        logger.info("Browser instance closed")


async def render_html_to_png(
    html_content: str,
    output_path: Optional[str] = None,
    width: int = 1080,
    height: int = 1080
) -> str:
    """
    Render HTML content to a PNG image.

    Args:
        html_content: Complete HTML content to render
        output_path: Optional output file path. If None, generates one.
        width: Image width in pixels (default: 1080)
        height: Image height in pixels (default: 1080)

    Returns:
        Path to the generated PNG file
    """
    # Generate output path if not provided
    if output_path is None:
        settings.ensure_directories()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(settings.outputs_dir / f"visual_{timestamp}.png")

    logger.info(f"Rendering HTML to PNG: {output_path}")

    try:
        browser = await get_browser()
        context = await browser.new_context(
            viewport={'width': width, 'height': height},
            device_scale_factor=2  # For retina quality
        )
        page = await context.new_page()

        # Set the HTML content
        await page.set_content(html_content, wait_until='networkidle')

        # Wait a bit for any CSS animations to settle
        await asyncio.sleep(0.5)

        # Take screenshot
        await page.screenshot(
            path=output_path,
            type='png',
            clip={'x': 0, 'y': 0, 'width': width, 'height': height}
        )

        await context.close()

        logger.info(f"PNG rendered successfully: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Failed to render HTML to PNG: {e}")
        raise


async def render_html_file_to_png(
    html_path: str,
    output_path: Optional[str] = None,
    width: int = 1080,
    height: int = 1080
) -> str:
    """
    Render an HTML file to a PNG image.

    Args:
        html_path: Path to the HTML file
        output_path: Optional output file path
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Path to the generated PNG file
    """
    html_file = Path(html_path)
    if not html_file.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    html_content = html_file.read_text(encoding='utf-8')
    return await render_html_to_png(html_content, output_path, width, height)


async def save_html_and_render(
    html_content: str,
    base_name: Optional[str] = None
) -> tuple[str, str]:
    """
    Save HTML content to file and render to PNG.

    Args:
        html_content: Complete HTML content
        base_name: Optional base name for files (without extension)

    Returns:
        Tuple of (html_path, png_path)
    """
    settings.ensure_directories()

    if base_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"visual_{timestamp}"

    html_path = str(settings.outputs_dir / f"{base_name}.html")
    png_path = str(settings.outputs_dir / f"{base_name}.png")

    # Save HTML
    Path(html_path).write_text(html_content, encoding='utf-8')
    logger.info(f"HTML saved: {html_path}")

    # Render to PNG
    await render_html_to_png(html_content, png_path)

    return html_path, png_path


# Cleanup function to be called on shutdown
async def cleanup():
    """Cleanup resources."""
    await close_browser()
