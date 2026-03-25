"""
Centralized configuration for AI Creator OS.
All settings are loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    # ── OpenAI ──────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    OPENAI_MODEL: str = Field("gpt-4o", description="Default LLM model")
    OPENAI_TEMPERATURE: float = Field(0.7, description="LLM temperature")

    # ── Supabase ─────────────────────────────────────────────────────────────
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_KEY: str = Field(..., description="Supabase anon/service key")

    # ── Apify ─────────────────────────────────────────────────────────────────
    APIFY_API_TOKEN: str = Field(..., description="Apify API token for scraping")
    APIFY_LINKEDIN_ACTOR: str = Field(
        "curious_coder/linkedin-post-search-scraper",
        description="Apify actor ID for LinkedIn scraping",
    )
    APIFY_REDDIT_ACTOR: str = Field(
        "trudax/reddit-scraper-lite",
        description="Apify actor ID for Reddit scraping",
    )

    # ── Instagram Graph API ───────────────────────────────────────────────────
    INSTAGRAM_APP_ID: str = Field(..., description="Meta App ID")
    INSTAGRAM_APP_SECRET: str = Field(..., description="Meta App Secret")
    INSTAGRAM_API_VERSION: str = Field("v19.0", description="Graph API version")

    # ── DALL-E / Image Generation ─────────────────────────────────────────────
    DALLE_MODEL: str = Field("dall-e-3", description="DALL-E model version")
    DALLE_IMAGE_SIZE: str = Field("1024x1024", description="Image dimensions")
    DALLE_IMAGE_QUALITY: str = Field("hd", description="Image quality: standard | hd")

    # ── Canva API (optional alternative to DALL-E) ────────────────────────────
    CANVA_API_TOKEN: Optional[str] = Field(None, description="Canva API token")

    # ── App Behaviour ─────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field("INFO", description="Logging level")
    MAX_POSTS_PER_PAGE_PER_DAY: int = Field(5, description="Max posts per page daily")
    TREND_SCAN_INTERVAL_HOURS: int = Field(6, description="How often to scan trends")
    ANALYTICS_INTERVAL_HOURS: int = Field(12, description="How often to pull metrics")
    LEARNING_INTERVAL_HOURS: int = Field(24, description="How often to run learner")
    DUPLICATE_WINDOW_DAYS: int = Field(30, description="Days to look back for dedup")
    ENGAGEMENT_SCORE_WINDOW_DAYS: int = Field(7, description="Days for learning window")

    # ── API Server ────────────────────────────────────────────────────────────
    API_HOST: str = Field("0.0.0.0", description="FastAPI host")
    API_PORT: int = Field(8000, description="FastAPI port")
    API_SECRET_KEY: str = Field("change-me-in-production", description="JWT secret")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


# Singleton
settings = Settings()
