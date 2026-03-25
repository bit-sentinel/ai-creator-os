# AI Creator OS — VPS Deployment Guide

Complete guide to deploying the AI Creator OS on a Ubuntu 22.04 VPS, from a fresh server to a fully running production system with SSL, process management, monitoring, and automated backups.

---

## Table of Contents

1. [Server Requirements](#1-server-requirements)
2. [Initial Server Setup](#2-initial-server-setup)
3. [Install System Dependencies](#3-install-system-dependencies)
4. [Clone & Configure the App](#4-clone--configure-the-app)
5. [Supabase Database Setup](#5-supabase-database-setup)
6. [Run with systemd (Recommended)](#6-run-with-systemd-recommended)
7. [Run with Docker Compose (Alternative)](#7-run-with-docker-compose-alternative)
8. [Nginx Reverse Proxy + SSL](#8-nginx-reverse-proxy--ssl)
9. [Deploy n8n](#9-deploy-n8n)
10. [Seed Your Instagram Accounts](#10-seed-your-instagram-accounts)
11. [Import n8n Workflows](#11-import-n8n-workflows)
12. [Monitoring & Logs](#12-monitoring--logs)
13. [Automated Backups](#13-automated-backups)
14. [Security Hardening](#14-security-hardening)
15. [Scaling to 10+ Pages](#15-scaling-to-10-pages)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Server Requirements

### Minimum spec (up to 3 accounts, 15 posts/day)
| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 2 GB | 4 GB |
| Disk | 20 GB SSD | 40 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| Network | 100 Mbps | 1 Gbps |

### Recommended scale (10+ accounts, 50+ posts/day)
- 4 vCPU / 8 GB RAM / 80 GB SSD
- Separate server for n8n (optional but cleaner)

### Recommended providers
- **Hetzner Cloud** — CX21 (€5/mo) for starter, CX31 (€10/mo) for scale
- **DigitalOcean** — Droplet 2 vCPU / 4 GB ($24/mo)
- **Vultr** — High Frequency 2 vCPU / 4 GB ($24/mo)
- **Linode / Akamai** — Shared 4 GB ($24/mo)

---

## 2. Initial Server Setup

### 2.1 — Connect as root and create a deploy user

```bash
# From your local machine
ssh root@YOUR_SERVER_IP

# On the server — create a non-root user
adduser deploy
usermod -aG sudo deploy

# Copy your SSH key to the new user
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy

# Log out and reconnect as deploy
exit
ssh deploy@YOUR_SERVER_IP
```

### 2.2 — Update the system

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    curl wget git unzip htop ufw fail2ban \
    build-essential libssl-dev libffi-dev \
    libpq-dev python3-pip python3-venv python3-dev
```

### 2.3 — Configure the firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp       # HTTP (for Let's Encrypt + redirect)
sudo ufw allow 443/tcp      # HTTPS
sudo ufw allow 8000/tcp     # AI Creator OS API (restrict later to nginx only)
sudo ufw allow 5678/tcp     # n8n UI
sudo ufw enable
sudo ufw status
```

### 2.4 — Set timezone to UTC

```bash
sudo timedatectl set-timezone UTC
timedatectl
```

---

## 3. Install System Dependencies

### 3.1 — Python 3.11

```bash
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 --version    # Python 3.11.x
```

### 3.2 — Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 3.3 — Certbot (Let's Encrypt SSL)

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 3.4 — Docker & Docker Compose (if using Docker deployment)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
newgrp docker

# Docker Compose v2
sudo apt install -y docker-compose-plugin
docker compose version
```

---

## 4. Clone & Configure the App

### 4.1 — Clone the repository

```bash
sudo mkdir -p /opt/creator-os
sudo chown deploy:deploy /opt/creator-os

git clone https://github.com/bit-sentinel/ai-creator-os.git /opt/creator-os
cd /opt/creator-os
```

### 4.2 — Create the Python virtual environment

```bash
python3.11 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 4.3 — Configure environment variables

```bash
cp .env.example .env
nano .env
```

Fill in every value:

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.7

# Supabase
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=eyJhbGci...

# Apify
APIFY_API_TOKEN=apify_api_...

# Instagram / Meta
INSTAGRAM_APP_ID=1234567890
INSTAGRAM_APP_SECRET=abc123...
INSTAGRAM_API_VERSION=v19.0

# DALL-E
DALLE_MODEL=dall-e-3
DALLE_IMAGE_SIZE=1024x1024
DALLE_IMAGE_QUALITY=hd

# App
LOG_LEVEL=INFO
MAX_POSTS_PER_PAGE_PER_DAY=5
TREND_SCAN_INTERVAL_HOURS=6
ANALYTICS_INTERVAL_HOURS=12
LEARNING_INTERVAL_HOURS=24

# API Server — use a strong random value
API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=$(openssl rand -hex 32)
```

> **Security:** Lock down the .env file immediately.
> ```bash
> chmod 600 /opt/creator-os/.env
> ```

### 4.4 — Create the image cache directory

```bash
mkdir -p /opt/creator-os/image_cache
```

### 4.5 — Verify the app starts cleanly

```bash
cd /opt/creator-os
source venv/bin/activate
python main.py --help
# Should print pipeline options without errors
```

---

## 5. Supabase Database Setup

### 5.1 — Create a Supabase project

1. Go to [supabase.com](https://supabase.com) → New project
2. Choose a region close to your VPS (latency matters)
3. Save the **Project URL** and **anon public key** — add them to `.env`
4. Go to **Settings → Database** and save the connection string too

### 5.2 — Run the schema

1. In Supabase → **SQL Editor** → New query
2. Open `database/schema.sql` locally and paste the full contents
3. Click **Run**
4. Verify tables were created: **Table Editor** should show `accounts`, `posts`, `trends`, `engagement_metrics`, `strategy_memory`, `content_templates`, `scheduled_jobs`

### 5.3 — Verify the fuzzy dedup function

```sql
-- Run this in Supabase SQL Editor to confirm pg_trgm + function work
SELECT check_topic_similarity('AI productivity tools', NOW() - INTERVAL '30 days', 0.7);
-- Should return: false (no data yet)
```

### 5.4 — Enable Row Level Security (production hardening)

```sql
-- Lock down all tables — only service role key can write
ALTER TABLE accounts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE posts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE trends           ENABLE ROW LEVEL SECURITY;
ALTER TABLE engagement_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_memory  ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_jobs   ENABLE ROW LEVEL SECURITY;

-- Allow full access for service role (used by your app)
CREATE POLICY "service_role_all" ON accounts         FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON posts            FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON trends           FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON engagement_metrics FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON strategy_memory  FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all" ON scheduled_jobs   FOR ALL USING (auth.role() = 'service_role');
```

> **Note:** Switch `SUPABASE_KEY` in `.env` from the `anon` key to the `service_role` key after enabling RLS.

---

## 6. Run with systemd (Recommended)

systemd keeps the API server alive across reboots and auto-restarts on crashes.

### 6.1 — Create the service file

```bash
sudo nano /etc/systemd/system/creator-os.service
```

Paste:

```ini
[Unit]
Description=AI Creator OS — FastAPI Server
Documentation=https://github.com/bit-sentinel/ai-creator-os
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/creator-os
EnvironmentFile=/opt/creator-os/.env
ExecStart=/opt/creator-os/venv/bin/python main.py --serve
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=creator-os

# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/opt/creator-os

[Install]
WantedBy=multi-user.target
```

### 6.2 — Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable creator-os
sudo systemctl start creator-os
sudo systemctl status creator-os
```

Expected output:
```
● creator-os.service - AI Creator OS — FastAPI Server
     Loaded: loaded (/etc/systemd/system/creator-os.service; enabled)
     Active: active (running) since ...
```

### 6.3 — Test the API is running

```bash
curl http://localhost:8000/health
# {"status":"ok","timestamp":"2026-03-25T..."}
```

### 6.4 — View live logs

```bash
sudo journalctl -u creator-os -f
# Ctrl+C to exit
```

---

## 7. Run with Docker Compose (Alternative)

Use this if you prefer container isolation or want n8n + the API bundled together.

### 7.1 — Configure and start

```bash
cd /opt/creator-os

# Make sure .env is filled in (same as Section 4.3)
# Change the n8n password before running
nano docker-compose.yml
# Edit: N8N_BASIC_AUTH_PASSWORD=your_strong_password

docker compose up -d
docker compose ps
```

### 7.2 — Check logs

```bash
docker compose logs -f creator-os
docker compose logs -f n8n
```

### 7.3 — Restart / update

```bash
# Pull latest code and rebuild
git pull origin main
docker compose build --no-cache
docker compose up -d
```

---

## 8. Nginx Reverse Proxy + SSL

Expose the API on `https://api.yourdomain.com` and n8n on `https://n8n.yourdomain.com`.

> **Prerequisite:** Point your DNS A records to your VPS IP before running Certbot.
> - `api.yourdomain.com` → VPS IP
> - `n8n.yourdomain.com` → VPS IP

### 8.1 — Creator OS API config

```bash
sudo nano /etc/nginx/sites-available/creator-os
```

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;   # long timeout for content generation
        proxy_send_timeout 600s;
        client_max_body_size 10M;
    }
}
```

### 8.2 — n8n config

```bash
sudo nano /etc/nginx/sites-available/n8n
```

```nginx
server {
    listen 80;
    server_name n8n.yourdomain.com;

    location / {
        proxy_pass         http://127.0.0.1:5678;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        client_max_body_size 16M;
    }
}
```

### 8.3 — Enable sites and get SSL certificates

```bash
sudo ln -s /etc/nginx/sites-available/creator-os /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/n8n        /etc/nginx/sites-enabled/

sudo nginx -t     # test config — must say "ok"
sudo systemctl reload nginx

# Issue certificates (replace with your domain and email)
sudo certbot --nginx -d api.yourdomain.com -d n8n.yourdomain.com \
    --non-interactive --agree-tos -m you@yourdomain.com

sudo systemctl reload nginx
```

### 8.4 — Verify HTTPS

```bash
curl https://api.yourdomain.com/health
# {"status":"ok","timestamp":"..."}
```

### 8.5 — Lock port 8000 to localhost only

```bash
sudo ufw delete allow 8000/tcp
# Port 8000 is now only reachable through nginx
```

---

## 9. Deploy n8n

### Option A — Docker Compose (already running if you used Section 7)

n8n is included in `docker-compose.yml`. Access it at `https://n8n.yourdomain.com`.

### Option B — systemd (standalone)

```bash
# Install n8n globally
sudo npm install -g n8n

sudo nano /etc/systemd/system/n8n.service
```

```ini
[Unit]
Description=n8n Workflow Automation
After=network.target

[Service]
Type=simple
User=deploy
Environment=N8N_BASIC_AUTH_ACTIVE=true
Environment=N8N_BASIC_AUTH_USER=admin
Environment=N8N_BASIC_AUTH_PASSWORD=YOUR_STRONG_PASSWORD
Environment=WEBHOOK_URL=https://n8n.yourdomain.com/
Environment=GENERIC_TIMEZONE=UTC
Environment=CREATOR_OS_API_URL=https://api.yourdomain.com
Environment=CREATOR_OS_API_KEY=YOUR_API_SECRET_KEY
Environment=SUPABASE_URL=https://YOUR_PROJECT.supabase.co
Environment=SUPABASE_KEY=YOUR_SUPABASE_KEY
ExecStart=/usr/bin/n8n start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable n8n
sudo systemctl start n8n
sudo systemctl status n8n
```

---

## 10. Seed Your Instagram Accounts

### 10.1 — Edit accounts.yaml

```bash
nano /opt/creator-os/config/accounts.yaml
```

Add your real Instagram page usernames, niches, and hashtag sets.

### 10.2 — Seed accounts to the database

```bash
cd /opt/creator-os
source venv/bin/activate
python scripts/setup_accounts.py
```

### 10.3 — Attach Instagram credentials

For each account, you need a **long-lived Instagram access token** and **Instagram User ID**.

**How to get them:**
1. Create a Meta App at [developers.facebook.com](https://developers.facebook.com)
2. Add the **Instagram Graph API** product
3. Get a short-lived token via Graph API Explorer
4. Exchange for a long-lived token (60-day expiry):

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token\
?grant_type=fb_exchange_token\
&client_id=YOUR_APP_ID\
&client_secret=YOUR_APP_SECRET\
&fb_exchange_token=SHORT_LIVED_TOKEN"
```

5. Get your Instagram User ID:

```bash
curl "https://graph.facebook.com/v19.0/me/accounts\
?access_token=LONG_LIVED_TOKEN"
```

6. Attach to each account:

```bash
python scripts/setup_accounts.py \
    --username ai_growth_hacks \
    --token "EAAx..." \
    --ig-user-id "17841400000000001"
```

> **Token refresh:** Long-lived tokens expire after 60 days. Refresh them before expiry:
> ```bash
> curl "https://graph.facebook.com/v19.0/oauth/access_token\
> ?grant_type=fb_exchange_token&client_id=APP_ID\
> &client_secret=APP_SECRET&fb_exchange_token=CURRENT_TOKEN"
> ```

---

## 11. Import n8n Workflows

### 11.1 — Set environment variables in n8n

Open `https://n8n.yourdomain.com` → **Settings → Variables** → Add each:

| Name | Value |
|---|---|
| `CREATOR_OS_API_URL` | `https://api.yourdomain.com` |
| `CREATOR_OS_API_KEY` | Value of `API_SECRET_KEY` from `.env` |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your Supabase service role key |

### 11.2 — Import the workflows

1. **Workflows** → top-right **⋮** menu → **Import from file**
2. Select `/opt/creator-os/workflows/n8n_workflows.json`
3. All 6 workflows will be created

### 11.3 — Activate in order

1. **AI Creator OS — Error Handler** — activate first (others reference it)
2. **AI Creator OS — 4. Engagement Analytics**
3. **AI Creator OS — 5. Learning & Optimization**
4. **AI Creator OS — 1. Trend Discovery**
5. **AI Creator OS — 2. Content Creation**
6. **AI Creator OS — 3. Publishing**

### 11.4 — Run a manual test

In n8n, open **Trend Discovery** → click **Execute Workflow** → watch the logs.

Then check Supabase → `trends` table — you should see new rows appear.

---

## 12. Monitoring & Logs

### Application logs

```bash
# Live log stream
sudo journalctl -u creator-os -f

# Last 200 lines
sudo journalctl -u creator-os -n 200

# Logs since a specific time
sudo journalctl -u creator-os --since "2026-03-25 08:00:00"

# Application log file
tail -f /opt/creator-os/creator_os.log
```

### System resource monitoring

```bash
# CPU / RAM / processes
htop

# Disk usage
df -h
du -sh /opt/creator-os/image_cache/   # monitor image cache size

# Network connections
ss -tlnp | grep -E '8000|5678'
```

### Supabase dashboard monitoring

- **Table Editor** — check row counts in `posts`, `trends`, `engagement_metrics`
- **Logs → API** — monitor query patterns and slow queries
- **Reports** — database size growth

### Set up a simple uptime check (optional)

```bash
# Add to crontab: check every 5 minutes, restart if down
crontab -e
```

Add this line:
```
*/5 * * * * curl -sf http://localhost:8000/health || sudo systemctl restart creator-os
```

---

## 13. Automated Backups

### 13.1 — Image cache backup script

```bash
sudo nano /opt/creator-os/scripts/backup.sh
```

```bash
#!/usr/bin/env bash
set -e

BACKUP_DIR="/var/backups/creator-os"
DATE=$(date +%Y-%m-%d_%H-%M)
mkdir -p "$BACKUP_DIR"

# Backup image cache (compress)
tar -czf "$BACKUP_DIR/image_cache_$DATE.tar.gz" \
    -C /opt/creator-os image_cache/ creator_os.log

# Keep only the last 7 days of backups
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

echo "Backup complete: $BACKUP_DIR/image_cache_$DATE.tar.gz"
```

```bash
chmod +x /opt/creator-os/scripts/backup.sh
```

### 13.2 — Schedule daily backup

```bash
sudo crontab -e
```

Add:
```
0 4 * * * /opt/creator-os/scripts/backup.sh >> /var/log/creator-os-backup.log 2>&1
```

> **Note:** Supabase handles its own automated backups (daily on free plan, point-in-time on Pro). The local backup covers generated images and logs only.

---

## 14. Security Hardening

### 14.1 — SSH hardening

```bash
sudo nano /etc/ssh/sshd_config
```

Set / confirm these lines:
```
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
Port 22
```

```bash
sudo systemctl restart sshd
```

### 14.2 — Fail2ban (auto-block brute force)

```bash
sudo nano /etc/fail2ban/jail.local
```

```ini
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port    = ssh
logpath = /var/log/auth.log

[nginx-http-auth]
enabled = true
```

```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
sudo fail2ban-client status
```

### 14.3 — Restrict API access by IP (optional)

If n8n and the API are on the same server, block external access to port 8000 entirely:

```bash
sudo ufw delete allow 8000/tcp
# Already done in Section 8.5 — confirm it's closed
sudo ufw status | grep 8000
```

### 14.4 — Rotate the API secret key

```bash
# Generate a new key
openssl rand -hex 32

# Update .env
nano /opt/creator-os/.env
# Update API_SECRET_KEY=<new_value>

# Restart the service
sudo systemctl restart creator-os

# Update the variable in n8n too
# n8n → Settings → Variables → CREATOR_OS_API_KEY
```

### 14.5 — Keep secrets out of logs

Verify `.env` is in `.gitignore`:
```bash
cd /opt/creator-os
git check-ignore -v .env
# .gitignore:1:.env    .env
```

---

## 15. Scaling to 10+ Pages

### Increase Uvicorn workers

By default the API runs with 1 worker. For 10+ accounts with concurrent requests, increase workers:

```bash
sudo nano /etc/systemd/system/creator-os.service
```

Change:
```ini
ExecStart=/opt/creator-os/venv/bin/python main.py --serve
```

To:
```ini
ExecStart=/opt/creator-os/venv/bin/uvicorn api.routes:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart creator-os
```

### Tune Supabase connection pool

For 10+ concurrent accounts, enable pgBouncer in Supabase:
- **Supabase Dashboard → Settings → Database → Connection Pooling**
- Mode: **Transaction** (best for short API calls)
- Update `SUPABASE_KEY` to use the pooler connection string

### Image cache storage

Generated images accumulate fast. Options:
1. **Increase disk** — easiest (add a volume in your cloud provider)
2. **Upload to S3/R2** — update `image_generator.py` to upload instead of saving locally:

```bash
pip install boto3
```

```python
# In services/image_generator.py — add after _download_and_cache
import boto3

def _upload_to_s3(self, local_path: Path) -> str:
    s3 = boto3.client("s3")
    key = f"carousel-images/{local_path.name}"
    s3.upload_file(str(local_path), "your-bucket", key)
    return f"https://your-bucket.s3.amazonaws.com/{key}"
```

### Run pipelines in parallel (advanced)

For very high volume, split accounts across multiple servers and use a shared Supabase database. Each server runs its own API instance with a subset of accounts, all managed from a single n8n instance.

---

## 16. Troubleshooting

### API won't start

```bash
# Check the error
sudo journalctl -u creator-os -n 50 --no-pager

# Most common causes:
# 1. Missing .env values
cd /opt/creator-os && source venv/bin/activate && python -c "from config.settings import settings; print('OK')"

# 2. Port already in use
sudo ss -tlnp | grep 8000

# 3. Python import error
python main.py --pipeline trend_discovery 2>&1 | head -30
```

### n8n can't reach the API

```bash
# Test from the n8n server (or same server)
curl -s -X POST http://localhost:8000/pipelines/trend-discovery \
    -H "x-api-key: YOUR_KEY" \
    -H "Content-Type: application/json" \
    -d '{"account": null}'

# Check nginx is proxying correctly
sudo nginx -t && sudo systemctl status nginx
```

### Supabase connection errors

```bash
# Test connection directly
cd /opt/creator-os && source venv/bin/activate
python -c "
from services.supabase_client import get_db
db = get_db()
res = db.table('accounts').select('count').execute()
print('DB OK:', res)
"
```

### Apify scraper timeouts

The scrapers poll until the actor run completes (max 5 minutes). If consistently timing out:
- Check your Apify dashboard for failed runs
- Increase `MAX_WAIT` in `linkedin_scraper.py` and `reddit_scraper.py`
- Verify your Apify token has sufficient compute units

### Instagram publish failures

```bash
# Check the error_log column in the posts table
# Supabase → Table Editor → posts → filter status = 'failed'

# Common errors:
# "Invalid token" → refresh the long-lived token
# "Media upload failed" → DALL-E image URL expired (re-run design agent)
# "Rate limit" → reduce posting frequency in accounts.yaml
```

### Image cache filling up disk

```bash
# Check size
du -sh /opt/creator-os/image_cache/

# Clear images older than 7 days
find /opt/creator-os/image_cache/ -name "*.png" -mtime +7 -delete

# Add to crontab to auto-clean weekly
(crontab -l ; echo "0 5 * * 0 find /opt/creator-os/image_cache/ -name '*.png' -mtime +7 -delete") | crontab -
```

### Check the full pipeline health in one command

```bash
echo "=== Service ===" && sudo systemctl is-active creator-os
echo "=== API ===" && curl -sf http://localhost:8000/health | python3 -m json.tool
echo "=== Disk ===" && df -h /opt/creator-os
echo "=== Image cache ===" && du -sh /opt/creator-os/image_cache/
echo "=== Last 10 log lines ===" && sudo journalctl -u creator-os -n 10 --no-pager
```

---

## Quick Reference — Common Commands

```bash
# Start / stop / restart the API
sudo systemctl start creator-os
sudo systemctl stop creator-os
sudo systemctl restart creator-os

# View live logs
sudo journalctl -u creator-os -f

# Run a pipeline manually
cd /opt/creator-os && source venv/bin/activate
python main.py --pipeline trend_discovery
python main.py --pipeline content_creation --account ai_growth_hacks
python main.py --pipeline all

# Update to latest code
cd /opt/creator-os
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart creator-os

# Check n8n status
sudo systemctl status n8n
sudo journalctl -u n8n -n 50

# Nginx
sudo nginx -t
sudo systemctl reload nginx
sudo certbot renew --dry-run    # test SSL renewal
```
