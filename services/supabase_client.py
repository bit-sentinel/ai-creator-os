"""
Supabase client — thin wrapper around the official Python client.
All DB interactions in the system go through this module.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone

from supabase import create_client, Client

from config.settings import settings

logger = logging.getLogger(__name__)


def _get_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


# Module-level singleton
_client: Optional[Client] = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = _get_client()
    return _client


# ─── Accounts ────────────────────────────────────────────────────────────────

def get_active_accounts() -> List[Dict]:
    res = get_db().table("accounts").select("*").eq("status", "active").execute()
    return res.data or []


def get_account(account_id: str) -> Optional[Dict]:
    res = get_db().table("accounts").select("*").eq("account_id", account_id).single().execute()
    return res.data


def upsert_account(data: Dict) -> Dict:
    res = get_db().table("accounts").upsert(data).execute()
    return res.data[0]


# ─── Trends ──────────────────────────────────────────────────────────────────

def save_trends(trends: List[Dict]) -> None:
    if not trends:
        return
    get_db().table("trends").upsert(trends, ignore_duplicates=True).execute()


def get_unused_trends(niche: str, limit: int = 10) -> List[Dict]:
    res = (
        get_db()
        .table("trends")
        .select("*")
        .eq("niche", niche)
        .eq("used", False)
        .order("viral_score", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def mark_trend_used(trend_id: str) -> None:
    get_db().table("trends").update({"used": True}).eq("trend_id", trend_id).execute()


def trend_topic_exists(topic: str, similarity_threshold: float = 0.7) -> bool:
    """Fuzzy dedup using pg_trgm similarity."""
    since = (datetime.now(timezone.utc) - timedelta(days=settings.DUPLICATE_WINDOW_DAYS)).isoformat()
    res = get_db().rpc(
        "check_topic_similarity",
        {"p_topic": topic, "p_since": since, "p_threshold": similarity_threshold},
    ).execute()
    return bool(res.data)


# ─── Posts ───────────────────────────────────────────────────────────────────

def create_post(data: Dict) -> Dict:
    res = get_db().table("posts").insert(data).execute()
    return res.data[0]


def update_post(post_id: str, data: Dict) -> Dict:
    res = get_db().table("posts").update(data).eq("post_id", post_id).execute()
    return res.data[0]


def get_post(post_id: str) -> Optional[Dict]:
    res = get_db().table("posts").select("*").eq("post_id", post_id).single().execute()
    return res.data


def get_scheduled_posts(account_id: str, before: Optional[datetime] = None) -> List[Dict]:
    q = (
        get_db()
        .table("posts")
        .select("*")
        .eq("account_id", account_id)
        .eq("status", "scheduled")
    )
    if before:
        q = q.lte("scheduled_at", before.isoformat())
    q = q.order("scheduled_at")
    return (q.execute()).data or []


def get_published_posts_since(account_id: str, days: int = 7) -> List[Dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    res = (
        get_db()
        .table("posts")
        .select("*,engagement_metrics(*)")
        .eq("account_id", account_id)
        .eq("status", "published")
        .gte("posted_at", since)
        .execute()
    )
    return res.data or []


def post_hash_exists(content_hash: str) -> bool:
    res = (
        get_db()
        .table("posts")
        .select("post_id")
        .eq("content_hash", content_hash)
        .limit(1)
        .execute()
    )
    return len(res.data) > 0


# ─── Engagement Metrics ───────────────────────────────────────────────────────

def save_metrics(metrics: List[Dict]) -> None:
    if not metrics:
        return
    get_db().table("engagement_metrics").upsert(metrics).execute()


def get_metrics_for_post(post_id: str) -> Optional[Dict]:
    res = (
        get_db()
        .table("engagement_metrics")
        .select("*")
        .eq("post_id", post_id)
        .order("collected_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


# ─── Strategy Memory ──────────────────────────────────────────────────────────

def get_strategy_memory(account_id: str) -> Optional[Dict]:
    res = (
        get_db()
        .table("strategy_memory")
        .select("*")
        .eq("account_id", account_id)
        .single()
        .execute()
    )
    return res.data


def upsert_strategy_memory(account_id: str, memory: Dict) -> Dict:
    memory["account_id"] = account_id
    memory["last_updated"] = datetime.now(timezone.utc).isoformat()
    res = (
        get_db()
        .table("strategy_memory")
        .upsert(memory, on_conflict="account_id")
        .execute()
    )
    return res.data[0]


# ─── Content Templates ────────────────────────────────────────────────────────

def get_templates(niche: Optional[str] = None) -> List[Dict]:
    q = get_db().table("content_templates").select("*").order("avg_engagement_score", desc=True)
    if niche:
        q = q.or_(f"niche.eq.{niche},niche.is.null")
    return (q.execute()).data or []


def increment_template_usage(template_id: str, new_score: float) -> None:
    """Update running average engagement score for a template."""
    tpl = get_db().table("content_templates").select("usage_count,avg_engagement_score").eq("template_id", template_id).single().execute().data
    if tpl:
        count = tpl["usage_count"] + 1
        avg = (tpl["avg_engagement_score"] * tpl["usage_count"] + new_score) / count
        get_db().table("content_templates").update({"usage_count": count, "avg_engagement_score": avg}).eq("template_id", template_id).execute()


# ─── Scheduled Jobs ──────────────────────────────────────────────────────────

def log_job(data: Dict) -> Dict:
    res = get_db().table("scheduled_jobs").insert(data).execute()
    return res.data[0]


def update_job(job_id: str, data: Dict) -> None:
    get_db().table("scheduled_jobs").update(data).eq("job_id", job_id).execute()
