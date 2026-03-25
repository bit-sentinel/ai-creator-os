"""Tests for FastAPI routes."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.routes import app

client = TestClient(app)

VALID_KEY = "test-secret-key"
HEADERS = {"x-api-key": VALID_KEY}


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert "timestamp" in resp.json()


class TestAuth:
    def test_missing_api_key_returns_422(self):
        resp = client.post("/pipelines/trend-discovery", json={})
        assert resp.status_code == 422   # FastAPI header validation

    def test_wrong_api_key_returns_401(self):
        resp = client.post(
            "/pipelines/trend-discovery",
            json={"account": None},
            headers={"x-api-key": "wrong-key"},
        )
        assert resp.status_code == 401


class TestPipelineEndpoints:
    PIPELINES = [
        "/pipelines/trend-discovery",
        "/pipelines/content-creation",
        "/pipelines/publishing",
        "/pipelines/analytics",
        "/pipelines/learning",
    ]

    @pytest.mark.parametrize("url", PIPELINES)
    def test_pipeline_queued(self, url):
        pipeline_name = url.split("/")[-1].replace("-", "_")
        mock_fn_path = f"main.run_{pipeline_name}"

        with patch(mock_fn_path):
            resp = client.post(url, json={"account": None}, headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"
        assert "started_at" in data

    @pytest.mark.parametrize("url", PIPELINES)
    def test_pipeline_with_account_filter(self, url):
        pipeline_name = url.split("/")[-1].replace("-", "_")
        with patch(f"main.run_{pipeline_name}"):
            resp = client.post(url, json={"account": "ai_growth_hacks"}, headers=HEADERS)

        assert resp.status_code == 200
        assert resp.json()["account_filter"] == "ai_growth_hacks"


class TestAccountsEndpoint:
    def test_returns_account_list(self):
        fake_accounts = [
            {"account_id": "aaa", "username": "test_acc", "niche": "AI & Productivity"}
        ]
        with patch("api.routes.db") as mock_db:
            mock_db.get_active_accounts.return_value = fake_accounts
            resp = client.get("/accounts", headers=HEADERS)

        assert resp.status_code == 200
        assert len(resp.json()["accounts"]) == 1

    def test_strategy_not_found_returns_404(self):
        with patch("api.routes.db") as mock_db:
            mock_db.get_active_accounts.return_value = []
            resp = client.get("/accounts/nonexistent/strategy", headers=HEADERS)

        assert resp.status_code == 404
