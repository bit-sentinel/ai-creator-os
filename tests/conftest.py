"""
Shared pytest fixtures for AI Creator OS tests.
Uses environment variable overrides so no real API keys are needed.
"""
import os
import pytest

# Patch all external credentials before any module import
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-supabase-key")
os.environ.setdefault("APIFY_API_TOKEN", "apify_fake_token")
os.environ.setdefault("INSTAGRAM_APP_ID", "123456")
os.environ.setdefault("INSTAGRAM_APP_SECRET", "fake_secret")
os.environ.setdefault("API_SECRET_KEY", "test-secret-key")


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_account():
    return {
        "account_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "username": "test_account",
        "platform": "instagram",
        "niche": "AI & Productivity",
        "posting_frequency": 5,
        "preferred_post_times": ["07:00", "12:00", "17:00"],
        "access_token": "fake_access_token",
        "instagram_user_id": "17841400000000001",
        "status": "active",
    }


@pytest.fixture
def sample_trend():
    return {
        "trend_id": "bbbbbbbb-0000-0000-0000-000000000001",
        "platform": "reddit",
        "topic": "5 AI tools that replace your entire marketing team",
        "source_url": "https://reddit.com/r/artificial/abc123",
        "viral_score": 88.5,
        "niche": "AI & Productivity",
        "used": False,
    }


@pytest.fixture
def sample_strategy_memory():
    return {
        "best_topics": [
            {"topic": "ChatGPT productivity hacks", "avg_score": 450.0, "sample_count": 3},
            {"topic": "AI tools for entrepreneurs", "avg_score": 380.0, "sample_count": 2},
        ],
        "best_hooks": [
            {"hook": "7 AI tools that changed how I work", "pattern": "NUMBER_LIST", "avg_score": 520.0},
            {"hook": "I wasted 6 months until I found these tools", "pattern": "STORY_OPEN", "avg_score": 410.0},
        ],
        "best_posting_times": [
            {"hour_utc": 7, "avg_score": 480.0},
            {"hour_utc": 17, "avg_score": 390.0},
        ],
        "best_carousel_format": {
            "optimal_slide_count": 5,
            "best_cta_type": "question",
            "best_slide1_style": "bold_stat",
        },
        "best_hashtags": [
            {"tag": "#AITools", "avg_reach": 12000},
            {"tag": "#ProductivityHacks", "avg_reach": 8500},
        ],
        "worst_topics": ["generic motivation", "vague business tips"],
        "performance_baseline": {
            "avg_engagement_score": 320.0,
            "avg_likes": 180,
            "avg_saves": 45,
        },
    }


@pytest.fixture
def sample_slides():
    return [
        {"slide_number": 1, "role": "hook",        "title": "7 AI Tools",        "content": "7 AI tools that will save you 10 hours every week.",    "image_url": "https://fake.cdn/1.png", "image_prompt": "Bold hook slide"},
        {"slide_number": 2, "role": "core_idea",   "title": "The Problem",       "content": "Most people waste hours on tasks AI can handle in seconds.", "image_url": "https://fake.cdn/2.png", "image_prompt": "Problem slide"},
        {"slide_number": 3, "role": "explanation", "title": "The Tools",         "content": "ChatGPT, Midjourney, Zapier, Notion AI, and more.",        "image_url": "https://fake.cdn/3.png", "image_prompt": "Tools list slide"},
        {"slide_number": 4, "role": "insight",     "title": "The Real Secret",   "content": "The edge isn't having AI. It's knowing how to prompt it.", "image_url": "https://fake.cdn/4.png", "image_prompt": "Insight slide"},
        {"slide_number": 5, "role": "cta",         "title": "Your Turn",         "content": "Save this. Which tool will you try first?",               "image_url": "https://fake.cdn/5.png", "image_prompt": "CTA slide"},
    ]
