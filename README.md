# AI Creator OS

An autonomous AI-powered content factory that discovers viral trends, generates Instagram carousel posts, publishes automatically, and continuously learns from engagement data.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI CREATOR OS                            │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │   Trend      │    │   Content    │    │     Design       │  │
│  │ Intelligence │───▶│  Generation  │───▶│     Engine       │  │
│  │   Engine     │    │   Engine     │    │  (DALL-E 3)      │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│         │                                         │             │
│    LinkedIn/Reddit                                ▼             │
│    (Apify API)                         ┌──────────────────┐    │
│                                        │   Publishing     │    │
│  ┌──────────────┐                      │    Engine        │    │
│  │  Analytics   │◀────── posts ────────│  (Instagram      │    │
│  │   Engine     │                      │   Graph API)     │    │
│  └──────────────┘                      └──────────────────┘    │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐    ┌──────────────────────────────────────┐  │
│  │  Learning &  │───▶│           Strategy Memory            │  │
│  │ Optimization │    │           (Supabase DB)               │  │
│  └──────────────┘    └──────────────────────────────────────┘  │
│                                                                 │
│  ─────────── Orchestrated by n8n Workflows ─────────────────── │
└─────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
ai-creator-os/
├── agents/
│   ├── base_agent.py          # Shared LLM + retry scaffolding
│   ├── trend_agent.py         # Discovers viral trends (LinkedIn + Reddit)
│   ├── hook_agent.py          # Generates 5 hook variants, selects best
│   ├── content_agent.py       # Writes 5-slide carousel content
│   ├── carousel_agent.py      # Structures slides + caption + hashtags
│   ├── design_agent.py        # Generates DALL-E 3 images per slide
│   ├── analytics_agent.py     # Fetches IG engagement metrics
│   └── learning_agent.py      # Analyses data, updates strategy memory
│
├── services/
│   ├── supabase_client.py     # All database operations
│   ├── linkedin_scraper.py    # Apify LinkedIn actor wrapper
│   ├── reddit_scraper.py      # Apify Reddit actor wrapper
│   ├── image_generator.py     # DALL-E 3 + Canva fallback
│   └── instagram_publisher.py # Instagram Graph API wrapper
│
├── api/
│   └── routes.py              # FastAPI endpoints (called by n8n)
│
├── workflows/
│   └── n8n_workflows.json     # Import into n8n directly
│
├── database/
│   └── schema.sql             # Run in Supabase SQL editor
│
├── config/
│   ├── settings.py            # Pydantic settings (env vars)
│   └── accounts.yaml          # Per-account configuration
│
├── main.py                    # CLI entry point + pipeline orchestrator
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Supabase account
- OpenAI account (GPT-4o + DALL-E 3)
- Apify account
- Meta Developer account (Instagram Graph API)
- n8n instance (self-hosted or cloud)

### 2. Installation

```bash
git clone <your-repo>
cd ai-creator-os
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your credentials in .env
```

### 3. Database Setup

In your Supabase project → SQL Editor, run:
```sql
-- Copy and paste the contents of database/schema.sql
```

Add the duplicate-check function:
```sql
CREATE OR REPLACE FUNCTION check_topic_similarity(
    p_topic TEXT,
    p_since TIMESTAMPTZ,
    p_threshold FLOAT DEFAULT 0.7
)
RETURNS BOOLEAN LANGUAGE SQL AS $$
    SELECT EXISTS (
        SELECT 1 FROM trends
        WHERE discovered_at > p_since
        AND similarity(topic, p_topic) > p_threshold
    )
    UNION ALL
    SELECT EXISTS (
        SELECT 1 FROM posts
        WHERE created_at > p_since
        AND similarity(topic, p_topic) > p_threshold
    )
    LIMIT 1;
$$;
```

### 4. Seed Your Accounts

Edit `config/accounts.yaml` with your Instagram page usernames and niches.

Then create them in the database:
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

### 5. Add Instagram Credentials

After setting up your Meta app and getting an access token, update each account:
```python
db.upsert_account({
    "username": "ai_growth_hacks",
    "access_token": "YOUR_LONG_LIVED_TOKEN",
    "instagram_user_id": "17841400000000000",
})
```

### 6. Start the API Server

```bash
python main.py --serve
# API running at http://localhost:8000
```

### 7. Import n8n Workflows

1. Open n8n → Workflows → Import from file
2. Select `workflows/n8n_workflows.json`
3. Set environment variables in n8n:
   - `CREATOR_OS_API_URL` = `http://your-server:8000`
   - `CREATOR_OS_API_KEY` = your API_SECRET_KEY from `.env`
   - `SUPABASE_URL` and `SUPABASE_KEY`
4. Activate all 5 workflows

---

## Running Manually

```bash
# Run all pipelines in sequence
python main.py --pipeline all

# Run individual pipelines
python main.py --pipeline trend_discovery
python main.py --pipeline content_creation
python main.py --pipeline publishing
python main.py --pipeline analytics
python main.py --pipeline learning

# Limit to one account
python main.py --pipeline content_creation --account ai_growth_hacks
```

---

## Automation Schedule (n8n)

| Workflow | Schedule | Description |
|---|---|---|
| Trend Discovery | Every 6 hours | Scan LinkedIn + Reddit |
| Content Creation | Daily at 02:00 UTC | Generate posts for all accounts |
| Publishing | Every 30 minutes | Publish scheduled posts |
| Analytics | Every 12 hours | Collect engagement metrics |
| Learning | Daily at 03:00 UTC | Update strategy memory |

---

## Engagement Score Formula

```
score = likes × 1 + comments × 3 + shares × 5 + saves × 4
```

The Learning Agent uses this score to identify top-performing content and update strategy memory for each account, so future posts are biased toward proven hooks, topics, and formats.

---

## Carousel Structure

| Slide | Role | Style |
|---|---|---|
| 1 | Hook | Viral opening (≤12 words) |
| 2 | Core Idea | Clear introduction |
| 3 | Explanation | Deep dive with examples |
| 4 | Insight | Surprising or actionable takeaway |
| 5 | CTA | Save / follow / question |

Max 25 words per slide. Educational tone.

---

## Deployment (Ubuntu / Cloud Server)

```bash
# Install system deps
sudo apt update && sudo apt install -y python3.11 python3.11-venv nginx

# Clone and set up
git clone <your-repo> /opt/creator-os
cd /opt/creator-os
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env && nano .env

# Run as a systemd service
sudo nano /etc/systemd/system/creator-os.service
```

`creator-os.service` contents:
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
3. Add Instagram credentials
4. The n8n workflows automatically iterate over all active accounts

For high volume (50+ pages), consider:
- Running multiple API server instances behind a load balancer
- Using Supabase connection pooling (pgBouncer)
- Processing accounts in parallel batches in n8n

---

## Future Improvements

1. **Multi-platform publishing** — TikTok, LinkedIn, Twitter/X
2. **A/B testing engine** — Test 2 hooks per post, learn which wins
3. **Video carousel** — Generate Reels using video generation APIs
4. **Competitor intelligence** — Monitor top accounts in each niche
5. **Auto-reply agent** — Respond to comments to boost engagement
6. **Revenue tracking** — Link content performance to affiliate/product sales
7. **Custom brand kits** — Per-account fonts, colours, logo overlays via Canva
8. **Human-in-the-loop** — Approval queue before auto-publishing
