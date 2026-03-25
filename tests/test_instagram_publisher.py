"""Tests for InstagramPublisher."""
from unittest.mock import MagicMock, patch, call

import pytest
import responses as resp_lib

from services.instagram_publisher import InstagramPublisher, GRAPH_BASE


class TestInstagramPublisher:
    @pytest.fixture
    def publisher(self):
        return InstagramPublisher(access_token="fake_token")

    def test_build_caption_with_hashtags(self, publisher):
        caption = publisher._build_caption("Test caption.", ["#AI", "#Tech"])
        assert "Test caption." in caption
        assert "#AI" in caption
        assert "#Tech" in caption

    def test_build_caption_limits_hashtags(self, publisher):
        tags = [f"#tag{i}" for i in range(50)]
        result = publisher._build_caption("caption", tags)
        # Should only include first 30
        tag_count = sum(1 for t in tags[:30] if t in result)
        assert tag_count == 30

    @resp_lib.activate
    def test_get_basic_metrics_success(self, publisher):
        resp_lib.add(
            resp_lib.GET,
            f"{GRAPH_BASE}/ig_media_123",
            json={"like_count": 150, "comments_count": 25},
            status=200,
        )
        metrics = publisher._get_basic_metrics("ig_media_123")
        assert metrics["like_count"] == 150
        assert metrics["comments_count"] == 25

    @resp_lib.activate
    def test_raise_for_graph_error_on_400(self, publisher):
        resp_lib.add(
            resp_lib.GET,
            f"{GRAPH_BASE}/bad_id",
            json={"error": {"message": "Invalid token", "code": 190}},
            status=400,
        )
        with pytest.raises(RuntimeError, match="Instagram Graph API error 190"):
            publisher._get_basic_metrics("bad_id")

    def test_create_image_container_posts_correct_params(self, publisher):
        with patch("services.instagram_publisher.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                json=lambda: {"id": "container_123"},
                raise_for_status=lambda: None,
                status_code=200,
            )
            container_id = publisher._create_image_container(
                "user_123", "https://fake.cdn/img.png", is_carousel_item=True
            )

        assert container_id == "container_123"
        call_kwargs = mock_post.call_args
        assert "image_url" in call_kwargs[1]["params"]
        assert call_kwargs[1]["params"]["is_carousel_item"] == "true"
