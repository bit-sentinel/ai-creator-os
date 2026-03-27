# AI Creator OS

An autonomous AI-powered content factory that discovers viral AI news, generates cinematic Instagram carousel posts with text overlays, publishes automatically, and continuously learns from engagement data.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AI CREATOR OS                               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  AI NEWS STORYTELLING ENGINE                 │    │
│  │                                                              │    │
│  │  HackerNews ──┐                                             │    │
│  │               ├──▶ NewsDetector ──▶ ViralityScorer          │    │
│  │  Reddit AI ───┘         │                  │                │    │
│  │                         ▼                  ▼                │    │
│  │                    ViralHook ──▶ VisualStory ──▶ ImagePrompt│    │
│  │                         │                                   │    │
│  │                         ▼                                   │    │
│  │              Stability AI (cinematic image gen)             │    │
│  │                         │                                   │    │
│  │                         ▼                                   │    │
│  │              Text Overlay (hook + watermark)                │    │
│  │                         │                                   │    │
│  │                         ▼                                   │    │
│  │              Caption + Hashtag Agents                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│  ┌───────────────────────────▼─────────────────────────────────┐    │
│  │                  CLASSIC CAROUSEL PIPELINE                   │    │
│  │  LinkedIn/Reddit ──▶ TrendAgent ──▶ HookAgent ──▶ Content   │    │
│  │  (Apify API)                     CarouselAgent ──▶ Design   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│                 ┌────────────────────────┐                           │
│                 │   Publishing Engine    │                           │
│                 │  Instagram Graph API   │                           │
│                 │  Single / Carousel /   │                           │
│                 │  Reel                  │                           │
│                 └────────────────────────┘                           │
│                              │                                       │
│              ┌───────────────┴──────────────┐                        │
│              ▼                              ▼                        │
│     ┌──────────────┐              ┌──────────────────┐               │
│     │  Analytics   │              │  Learning &      │               │
│     │   Engine     │              │  Optimization    │               │
│     └──────────────┘              └──────────────────┘               │
│                                                                      │
│  ──────────────── Orchestrated by n8n Workflows ─────────────────── │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
ai-creator-os/
├── agents/
│   ├── base_agent.py           # Shared LLM + retry + JSON parsing scaffolding
│   ├── news_detector_agent.py  # Filters scraped posts for high-impact AI stories
│   ├── virality_scorer_agent.py# Scores stories on shock/curiosity/visual/relevance
│   ├── viral_hook_agent.py     # 3-line dramatic hook generator
│   ├── visual_story_agent.py   # Converts hook to cinematic scene concept
│   ├── image_prompt_agent.py   # Builds Stability AI image prompt
│   ├── caption_agent.py        # 1-2 line punchy caption writer
│   ├── hashtag_agent.py        # 8-10 targeted hashtags
│   ├── trend_agent.py          # Discovers viral trends (LinkedIn + Reddit)
│   ├── hook_agent.py           # Generates 5 hook variants, selects best
│   ├── content_agent.py        # Writes 5-slide carousel content
│   ├── carousel_agent.py       # Structures slides + caption + hashtags
│   ├── design_agent.py         # Enhances image prompts (cinematic/cyberpunk style)
│   ├── analytics_agent.py      # Fetches IG engagement metrics
│   └── learning_agent.py       # Analyses data, updates strategy memory
│
├── services/
│   ├── supabase_client.py      # All database operations
│   ├── hackernews_scraper.py   # HN top stories via public Firebase API (no auth)
│   ├── reddit_scraper.py       # Apify Reddit actor wrapper
│   ├── linkedin_scraper.py     # Apify LinkedIn actor wrapper
│   ├── image_generator.py      # Stability AI image gen + Supabase Storage upload
│   ├── text_overlay.py         # PIL-based hook text + watermark overlay
│   ├── audio_generator.py      # edge-tts TTS voiceover (free, no API key)
│   ├── video_creator.py        # moviepy: image + audio → vertical MP4 Reel
│   └── instagram_publisher.py  # Instagram Graph API (single / carousel / reel)
│
├── scripts/
│   ├── post_carousel_news.py   # Scrape → generate → overlay → publish carousel
│   ├── repost_with_audio.py    # Repost latest post with text overlay as photo
│   ├── run_publish_one.py      # Publish one scheduled post from the DB
│   ├── post_single_fact.py     # Post a single fact/image manually
│   └── setup_accounts.py       # Seed accounts from accounts.yaml into DB
│
├── api/
│   └── routes.py               # FastAPI endpoints (called by n8n)
│
├── workflows/
│   └── n8n_workflows.json      # Import into n8n directly (6 workflows)
│
├── database/
│   └── schema.sql              # Run in Supabase SQL editor
│
├── config/
│   ├── settings.py             # Pydantic settings (env vars)
│   └── accounts.yaml           # Per-account configuration
│
├── ai_news_pipeline.py         # AI News pipeline orchestrator
├── main.py                     # CLI entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Supabase account (free tier works)
- Anthropic API key (Claude Sonnet)
- Stability AI API key (image generation)
- Apify account (Reddit/LinkedIn scraping)
- Meta Developer account (Instagram Graph API)
- n8n instance (self-hosted or cloud)

### 2. Installation

```bash
git clone https://github.com/bit-sentinel/ai-creator-os.git
cd ai-creator-os
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your credentials in .env
```

### 3. Environment Variables

Key variables in `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
STABILITY_API_KEY=sk-...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...   # Service role key — needed for Storage uploads
APIFY_API_TOKEN=apify_api_...
API_SECRET_KEY=your-secret
```

> **Supabase Storage:** Create a public bucket named `post-images` in your Supabase Dashboard → Storage before running image pipelines.

### 4. Database Setup

In your Supabase project → SQL Editor, run:
```sql
-- Copy and paste the contents of database/schema.sql
```

### 5. Seed Your Accounts

Edit `config/accounts.yaml` with your Instagram page usernames and niches, then:

```bash
python scripts/setup_accounts.py
```

Or manually:
```bash
python -c "
import yaml
from services import supabase_client as db
with open('config/accounts.yaml') as f:
    cfg = yaml.safe_load(f)
for acc in cfg['accounts']:
    db.upsert_account(acc)
    print(f'Created: {acc[\"username\"]}')
"
```

### 6. Add Instagram Credentials

After getting a long-lived token from Meta:
```python
from services import supabase_client as db
db.upsert_account({
    "username": "your_account",
    "access_token": "YOUR_LONG_LIVED_TOKEN",
    "instagram_user_id": "17841400000000000",
})
```

### 7. Start the API Server

```bash
python main.py --serve
# API running at http://localhost:8000
```

### 8. Import n8n Workflows

1. Open n8n → Workflows → Import from file
2. Select `workflows/n8n_workflows.json`
3. Set environment variables in n8n:
   - `CREATOR_OS_API_URL` = `http://your-server:8000`
   - `CREATOR_OS_API_KEY` = your `API_SECRET_KEY` from `.env`
4. Activate all 6 workflows

---

## Running Manually

```bash
# AI News pipeline — scrape live AI news, generate + publish
python main.py --pipeline ai_news
python main.py --pipeline ai_news --account cognitionlabs.ai
python main.py --pipeline ai_news --skip-images   # test without using credits

# Post a fresh AI news carousel directly (scrape → generate → overlay → publish)
python scripts/post_carousel_news.py --account cognitionlabs.ai
python scripts/post_carousel_news.py --account cognitionlabs.ai --skip-images

# Repost latest DB post as a single photo with hook text overlay
python scripts/repost_with_audio.py --account cognitionlabs.ai
python scripts/repost_with_audio.py --account cognitionlabs.ai --post-id <uuid>

# Classic carousel pipeline
python main.py --pipeline trend_discovery
python main.py --pipeline content_creation
python main.py --pipeline publishing
python main.py --pipeline analytics
python main.py --pipeline learning

# Publish one scheduled post from DB
python scripts/run_publish_one.py --account cognitionlabs.ai
```

---

## AI News Pipeline

The AI News Storytelling Engine (`ai_news_pipeline.py`) turns breaking AI developments into viral Instagram content automatically:

| Stage | Agent/Service | What it does |
|---|---|---|
| 1. Scrape | HackerNewsScraper + RedditScraper | Top AI stories from HN + r/artificial, r/MachineLearning, r/ChatGPT |
| 2. Detect | NewsDetectorAgent | Filters for high-impact AI stories only |
| 3. Score | ViralityScorerAgent | Scores on shock / curiosity / visual / relevance (0–100) |
| 4. Hook | ViralHookAgent | 3-line dramatic hook (shocking → what happened → consequence) |
| 5. Visual | VisualStoryAgent | Cinematic scene concept (subject, emotion, color palette) |
| 6. Image | ImagePromptAgent + Stability AI | Generates a cyberpunk/cinematic image |
| 7. Overlay | TextOverlayService | Adds hook text at bottom + @username watermark |
| 8. Caption | CaptionAgent + HashtagAgent | 1-2 line caption + 8-10 hashtags |
| 9. Publish | InstagramPublisher | Carousel (3 slides) or single photo |

### Carousel structure (AI News)

| Slide | Text overlay |
|---|---|
| 1 | Hook Line 1 — the shocking statement |
| 2 | Hook Line 2 — what actually happened |
| 3 | Hook Line 3 — the consequence / why it matters |

Each slide uses the same base image with a different text overlay.

---

## Automation Schedule (n8n)

| # | Workflow | Schedule | Description |
|---|---|---|---|
| 1 | Trend Discovery | Every 6 hours | Scan LinkedIn + Reddit for trending topics |
| 2 | Content Creation | Daily at 02:00 UTC | Generate classic carousel posts |
| 3 | Publishing | Every 30 minutes | Publish scheduled posts from DB |
| 4 | Analytics | Every 12 hours | Collect engagement metrics |
| 5 | Learning | Daily at 03:00 UTC | Update strategy memory |
| 6 | AI News Pipeline | Every 4 hours (06:00–23:00 UTC) | Scrape + generate + publish AI news |

---

## Image Style

All images are generated using **Stability AI** with a cinematic cyberpunk aesthetic:

- Ultra-realistic, 8K, dramatic shadows, high contrast
- Glowing neon highlights, dark backgrounds
- Sharp focus, depth of field
- No text rendered in the image (text added via overlay)

---

## Text Overlay

The `TextOverlayService` uses PIL (Pillow) to add:

- **Hook text** — Impact font, white with black stroke, centered at the bottom of the image on a dark gradient overlay
- **@username watermark** — smaller Impact font, bottom-left corner

---

## Engagement Score Formula

```
score = likes × 1 + comments × 3 + shares × 5 + saves × 4
```

The Learning Agent uses this to identify top-performing content and update strategy memory per account, so future posts are biased toward proven hooks, topics, and formats.

---

## Deployment (Ubuntu / Cloud Server)

```bash
# Install system deps
sudo apt update && sudo apt install -y python3.11 python3.11-venv nginx

# Clone and set up
git clone https://github.com/bit-sentinel/ai-creator-os.git /opt/creator-os
cd /opt/creator-os
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env && nano .env

# Run as a systemd service
sudo nano /etc/systemd/system/creator-os.service
```

`creator-os.service`:
```ini
[Unit]
Description=AI Creator OS API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/creator-os
EnvironmentFile=/opt/creator-os/.env
ExecStart=/opt/creator-os/venv/bin/python main.py --serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable creator-os
sudo systemctl start creator-os
sudo systemctl status creator-os
```

---

## Scaling to 10+ Pages

The system handles multiple accounts natively. To add more:

1. Add entries to `config/accounts.yaml`
2. Seed them to the database
3. Add Instagram credentials per account
4. The n8n workflows automatically iterate over all active accounts

For high volume (50+ pages):
- Run multiple API server instances behind a load balancer
- Use Supabase connection pooling (pgBouncer)
- Process accounts in parallel batches in n8n

---

## Roadmap

- [x] Classic carousel pipeline (trend → hook → content → design → publish)
- [x] AI News Storytelling Engine (HN + Reddit → viral hook → cinematic image → carousel)
- [x] Stability AI cinematic/cyberpunk image generation
- [x] Text overlay on images (hook + watermark)
- [x] TTS voiceover generation (edge-tts, free)
- [x] Reel video creation (image + audio, Ken Burns zoom)
- [ ] Multi-platform publishing — TikTok, LinkedIn, Twitter/X
- [ ] A/B testing engine — test 2 hooks per post, learn which wins
- [ ] Competitor intelligence — monitor top accounts in each niche
- [ ] Auto-reply agent — respond to comments to boost engagement
- [ ] Human-in-the-loop approval queue before auto-publishing
- [ ] Revenue tracking — link content performance to affiliate/product sales
