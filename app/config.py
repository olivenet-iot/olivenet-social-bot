"""
Olivenet Social Media Bot - Configuration

Centralized configuration with auto-detected paths.
All paths are derived from BASE_DIR which can be overridden via OLIVENET_BASE_DIR env var.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional


def detect_base_dir() -> Path:
    """
    Auto-detect the base directory for the project.
    Priority:
    1. OLIVENET_BASE_DIR environment variable
    2. /opt/olivenet-social-bot (production)
    3. Parent of this file's directory (development)
    """
    # Check env var first
    env_base = os.environ.get("OLIVENET_BASE_DIR")
    if env_base:
        return Path(env_base)

    # Check production path
    prod_path = Path("/opt/olivenet-social-bot")
    if prod_path.exists():
        return prod_path

    # Development: go up from app/config.py to project root
    current_file = Path(__file__).resolve()
    dev_path = current_file.parent.parent
    if (dev_path / "context").exists():
        return dev_path

    # Fallback to home directory path
    home_path = Path.home() / "olivenet-social-bot"
    if home_path.exists():
        return home_path

    # Ultimate fallback
    return prod_path


# Detect base directory before loading .env
BASE_DIR = detect_base_dir()

# Load .env from detected base directory
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Try alternate locations
    for alt_path in [Path.home() / "olivenet-social-bot" / ".env", Path("/opt/olivenet-social-bot/.env")]:
        if alt_path.exists():
            load_dotenv(alt_path)
            break


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Settings
    telegram_bot_token: str = Field(..., description="Telegram Bot API Token")
    telegram_admin_chat_id: int = Field(..., description="Admin chat ID for notifications")
    telegram_admin_user_ids: str = Field(default="", description="Comma-separated list of admin user IDs (empty = use admin_chat_id only)")

    @property
    def admin_user_ids(self) -> list:
        """Get list of admin user IDs for authorization."""
        ids = []
        # Always include the primary admin chat ID
        if self.telegram_admin_chat_id:
            ids.append(self.telegram_admin_chat_id)

        # Add any additional admin IDs from comma-separated list
        if self.telegram_admin_user_ids:
            for id_str in self.telegram_admin_user_ids.split(","):
                try:
                    user_id = int(id_str.strip())
                    if user_id not in ids:
                        ids.append(user_id)
                except ValueError:
                    pass
        return ids

    # Instagram API Settings (graph.instagram.com v21.0)
    instagram_access_token: str = Field(default="", description="Instagram Access Token")
    instagram_user_id: str = Field(default="", description="Instagram User ID")
    instagram_business_id: str = Field(default="", description="Instagram Business Account ID")

    # Meta Ads API Settings (for paid campaign tracking)
    meta_ad_account_id: str = Field(default="", description="Meta Ad Account ID (format: act_XXXXXXXXXX)")
    meta_business_id: str = Field(default="", description="Meta Business Manager ID")

    # Gemini AI Settings
    gemini_api_key: str = Field(default="", description="Gemini API Key for realistic image generation")

    # Replicate AI Settings
    replicate_api_token: str = Field(default="", description="Replicate API Token for Flux image generation")

    # OpenAI Settings (Sora)
    openai_api_key: str = Field(default="", description="OpenAI API Key for Sora video generation")

    # Cloudinary Settings
    cloudinary_cloud_name: str = Field(default="", description="Cloudinary cloud name")
    cloudinary_api_key: str = Field(default="", description="Cloudinary API key")
    cloudinary_api_secret: str = Field(default="", description="Cloudinary API secret")

    # imgbb Settings
    imgbb_api_key: str = Field(default="", description="imgbb API key for image CDN")

    # FLUX Settings
    flux_api_key: str = Field(default="", description="FLUX API key")

    # FAL.ai Settings (Kling video generation)
    fal_api_key: str = Field(default="", description="FAL API key for Kling video generation")

    # ElevenLabs TTS Settings
    elevenlabs_api_key: str = Field(default="", description="ElevenLabs API key for TTS")
    elevenlabs_voice_id: str = Field(default="", description="Default Turkish voice ID")
    elevenlabs_model: str = Field(default="eleven_multilingual_v2", description="TTS model")
    tts_stability: float = Field(default=0.5, description="Voice stability (0.0-1.0)")
    tts_similarity_boost: float = Field(default=0.75, description="Voice similarity boost (0.0-1.0)")
    tts_speed: float = Field(default=1.0, description="Speech speed (0.5-2.0)")

    # ElevenLabs Conversational Reels Settings
    elevenlabs_voice_id_female: str = Field(default="EJGs6dWlD5VrB3llhBqB", description="Female Turkish voice ID for conversational reels")

    # Claude Code Settings
    claude_timeout_post: int = Field(default=60, description="Timeout for post generation (seconds)")
    claude_timeout_visual: int = Field(default=90, description="Timeout for visual generation (seconds)")
    claude_timeout_video: int = Field(default=120, description="Timeout for video prompt generation (seconds)")

    # API Timeouts
    api_timeout_default: int = Field(default=30, description="Default API timeout (seconds)")
    api_timeout_video: int = Field(default=300, description="Video API timeout (seconds)")
    api_timeout_insights: int = Field(default=60, description="Insights API timeout (seconds)")

    # Rate Limiting
    rate_limit_delay: float = Field(default=0.3, description="Delay between API calls (seconds)")
    rate_limit_carousel: float = Field(default=2.0, description="Delay between carousel items (seconds)")

    # Content Settings
    max_instagram_words: int = Field(default=120, description="Max words for Instagram posts")

    # Review & Scoring Thresholds
    min_review_score: float = Field(default=7.0, description="Minimum score to approve content")
    min_review_score_revise: float = Field(default=5.0, description="Minimum score for revision (below = reject)")
    min_review_score_autonomous: float = Field(default=7.0, description="Minimum score for autonomous publishing")
    min_viral_score: float = Field(default=10.0, description="Minimum viral score threshold")
    hook_underperformance_threshold: float = Field(default=5.0, description="Hook viral score below this = underperforming")

    # Reels/Content Mix
    reels_weekly_target: int = Field(default=7, description="Target Reels per week (58% of 12)")
    carousel_weekly_target: int = Field(default=2, description="Target Carousels per week")
    post_weekly_target: int = Field(default=3, description="Target Posts per week")

    # Subtitle Settings (Automatic subtitles for voice reels/long videos)
    subtitle_enabled: bool = Field(default=False, description="Enable automatic subtitle generation")
    whisper_model_size: str = Field(default="base", description="Whisper model size: tiny, base, small, medium, large")
    subtitle_font: str = Field(default="DejaVu Sans", description="Subtitle font name")
    subtitle_font_size: int = Field(default=48, description="Subtitle font size in pixels")
    subtitle_max_chars: int = Field(default=35, description="Max characters per subtitle line")
    subtitle_max_lines: int = Field(default=2, description="Max lines per subtitle")

    # Paths - All derived from BASE_DIR
    base_dir: Path = Field(default=BASE_DIR)

    @property
    def context_dir(self) -> Path:
        return self.base_dir / "context"

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "templates"

    @property
    def outputs_dir(self) -> Path:
        return self.base_dir / "outputs"

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "content.db"

    @property
    def agent_personas_dir(self) -> Path:
        return self.context_dir / "agent-personas"

    @property
    def env_path(self) -> Path:
        return self.base_dir / ".env"

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    def ensure_directories(self):
        """Ensure all required directories exist."""
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_context_file(self, filename: str) -> Path:
        """Get full path to a context file."""
        return self.context_dir / filename

    def get_persona_file(self, agent_name: str) -> Path:
        """Get full path to an agent persona file."""
        return self.agent_personas_dir / f"{agent_name}.md"

    def get_output_file(self, filename: str) -> Path:
        """Get full path to an output file."""
        return self.outputs_dir / filename


# Global settings instance
settings = Settings()

# Convenience exports
CONTEXT_DIR = settings.context_dir
TEMPLATES_DIR = settings.templates_dir
OUTPUTS_DIR = settings.outputs_dir
LOGS_DIR = settings.logs_dir
DATA_DIR = settings.data_dir
DATABASE_PATH = settings.database_path
