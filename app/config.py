"""
Olivenet Social Media Bot - Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# .env dosyasını manuel olarak yükle
load_dotenv("/opt/olivenet-social-bot/.env")
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Settings
    telegram_bot_token: str = Field(..., description="Telegram Bot API Token")
    telegram_admin_chat_id: int = Field(..., description="Admin chat ID for notifications")

    # Facebook Settings
    facebook_page_id: str = Field(default="", description="Facebook Page ID")
    facebook_access_token: str = Field(default="", description="Facebook Page Access Token")

    # Gemini AI Settings
    gemini_api_key: str = Field(default="", description="Gemini API Key for realistic image generation")

    # Replicate AI Settings
    replicate_api_token: str = Field(default="", description="Replicate API Token for Flux image generation")

    # Claude Code Settings
    claude_timeout_post: int = Field(default=60, description="Timeout for post generation (seconds)")
    claude_timeout_visual: int = Field(default=90, description="Timeout for visual generation (seconds)")

    # Paths
    base_dir: Path = Field(default=Path("/opt/olivenet-social-bot"))
    context_dir: Path = Field(default=Path("/opt/olivenet-social-bot/context"))
    templates_dir: Path = Field(default=Path("/opt/olivenet-social-bot/templates"))
    outputs_dir: Path = Field(default=Path("/opt/olivenet-social-bot/outputs"))

    model_config = {
        "env_file": "/opt/olivenet-social-bot/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    def ensure_directories(self):
        """Ensure all required directories exist."""
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
