"""
FastAPI REST API — exposes all pipelines as HTTP endpoints.
Called by n8n workflows to trigger automation steps.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel

from config.settings import settings
from services import supabase_client as db

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Creator OS API",
    description="Internal API for n8n workflow orchestration",
    version="1.0.0",
)


# ─── Auth middleware (simple API key check) ───────────────────────────────────

def _verify_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != settings.API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ─── Request / Response models ────────────────────────────────────────────────

class PipelineRequest(BaseModel):
    account: Optional[str] = None   # Filter by username; null = all accounts


class PipelineResponse(BaseModel):
    pipeline: str
    status: str
    started_at: str
    account_filter: Optional[str]


# ─── Pipeline endpoints ───────────────────────────────────────────────────────

@app.post("/pipelines/trend-discovery", response_model=PipelineResponse)
async def trigger_trend_discovery(
    req: PipelineRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)
    from main import run_trend_discovery
    background_tasks.add_task(run_trend_discovery, req.account)
    return _response("trend_discovery", req.account)


@app.post("/pipelines/content-creation", response_model=PipelineResponse)
async def trigger_content_creation(
    req: PipelineRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)
    from main import run_content_creation
    background_tasks.add_task(run_content_creation, req.account)
    return _response("content_creation", req.account)


@app.post("/pipelines/publishing", response_model=PipelineResponse)
async def trigger_publishing(
    req: PipelineRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)
    from main import run_publishing
    background_tasks.add_task(run_publishing, req.account)
    return _response("publishing", req.account)


@app.post("/pipelines/analytics", response_model=PipelineResponse)
async def trigger_analytics(
    req: PipelineRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)
    from main import run_analytics
    background_tasks.add_task(run_analytics, req.account)
    return _response("analytics", req.account)


@app.post("/pipelines/learning", response_model=PipelineResponse)
async def trigger_learning(
    req: PipelineRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)
    from main import run_learning
    background_tasks.add_task(run_learning, req.account)
    return _response("learning", req.account)


# ─── Health / Status ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/accounts")
async def list_accounts(x_api_key: str = Header(...)):
    _verify_key(x_api_key)
    accounts = db.get_active_accounts()
    return {
        "accounts": [
            {"account_id": a["account_id"], "username": a["username"], "niche": a["niche"]}
            for a in accounts
        ]
    }


@app.get("/accounts/{username}/strategy")
async def get_strategy(username: str, x_api_key: str = Header(...)):
    _verify_key(x_api_key)
    accounts = db.get_active_accounts()
    account = next((a for a in accounts if a["username"] == username), None)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    memory = db.get_strategy_memory(account["account_id"])
    return memory or {}


# ─── Utility ─────────────────────────────────────────────────────────────────

def _response(pipeline: str, account: Optional[str]) -> PipelineResponse:
    return PipelineResponse(
        pipeline=pipeline,
        status="queued",
        started_at=datetime.now(timezone.utc).isoformat(),
        account_filter=account,
    )
