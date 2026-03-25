"""
Instagram Publisher Service
────────────────────────────
Wraps the Meta Instagram Graph API to:
  - Upload carousel container
  - Publish posts
  - Schedule posts
  - Fetch post insights
"""
import logging
import time
from typing import Dict, List, Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

GRAPH_BASE = f"https://graph.facebook.com/{settings.INSTAGRAM_API_VERSION}"


class InstagramPublisher:
    """Instagram Graph API wrapper for publishing and analytics."""

    PUBLISH_POLL_INTERVAL = 3   # seconds
    PUBLISH_MAX_WAIT = 120      # seconds

    def __init__(self, access_token: str):
        self.token = access_token

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLISHING
    # ═══════════════════════════════════════════════════════════════════════

    def publish_carousel(
        self,
        ig_user_id: str,
        image_urls: List[str],
        caption: str,
        hashtags: List[str],
        scheduled_publish_time: Optional[int] = None,
    ) -> str:
        """
        Full carousel publish flow:
        1. Create child media containers (one per image)
        2. Create carousel container
        3. Publish (or schedule)

        Returns the Instagram media ID of the published post.
        """
        if not image_urls:
            raise ValueError("No image URLs provided for carousel")

        # Step 1 — child containers
        child_ids = []
        for url in image_urls:
            child_id = self._create_image_container(ig_user_id, url, is_carousel_item=True)
            child_ids.append(child_id)
            logger.info("Created child container: %s", child_id)

        # Step 2 — carousel container
        full_caption = self._build_caption(caption, hashtags)
        carousel_id = self._create_carousel_container(
            ig_user_id, child_ids, full_caption, scheduled_publish_time
        )
        logger.info("Created carousel container: %s", carousel_id)

        # Step 3 — publish
        post_id = self._publish_container(ig_user_id, carousel_id)
        logger.info("Published carousel: post_id=%s", post_id)
        return post_id

    def _create_image_container(
        self, ig_user_id: str, image_url: str, is_carousel_item: bool = False
    ) -> str:
        url = f"{GRAPH_BASE}/{ig_user_id}/media"
        params = {
            "image_url": image_url,
            "is_carousel_item": str(is_carousel_item).lower(),
            "access_token": self.token,
        }
        resp = requests.post(url, params=params, timeout=30)
        self._raise_for_graph_error(resp)
        return resp.json()["id"]

    def _create_carousel_container(
        self,
        ig_user_id: str,
        children: List[str],
        caption: str,
        scheduled_time: Optional[int],
    ) -> str:
        url = f"{GRAPH_BASE}/{ig_user_id}/media"
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption[:2200],   # IG caption limit
            "access_token": self.token,
        }
        if scheduled_time:
            params["scheduled_publish_time"] = scheduled_time
            params["published"] = "false"
        resp = requests.post(url, params=params, timeout=30)
        self._raise_for_graph_error(resp)
        return resp.json()["id"]

    def _publish_container(self, ig_user_id: str, container_id: str) -> str:
        """Publish a container and wait for confirmation."""
        # Poll until container is ready
        self._wait_for_container(container_id)

        url = f"{GRAPH_BASE}/{ig_user_id}/media_publish"
        params = {
            "creation_id": container_id,
            "access_token": self.token,
        }
        resp = requests.post(url, params=params, timeout=30)
        self._raise_for_graph_error(resp)
        return resp.json()["id"]

    def _wait_for_container(self, container_id: str) -> None:
        """Poll container status until FINISHED or error."""
        url = f"{GRAPH_BASE}/{container_id}"
        elapsed = 0
        while elapsed < self.PUBLISH_MAX_WAIT:
            resp = requests.get(
                url,
                params={"fields": "status_code", "access_token": self.token},
                timeout=15,
            )
            self._raise_for_graph_error(resp)
            status = resp.json().get("status_code", "")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Container {container_id} status: {status}")
            time.sleep(self.PUBLISH_POLL_INTERVAL)
            elapsed += self.PUBLISH_POLL_INTERVAL
        raise TimeoutError(f"Container {container_id} not ready after {self.PUBLISH_MAX_WAIT}s")

    # ═══════════════════════════════════════════════════════════════════════
    # ANALYTICS
    # ═══════════════════════════════════════════════════════════════════════

    def get_post_insights(self, ig_media_id: str) -> Dict:
        """Fetch engagement metrics for a published post."""
        metrics = "like_count,comments_count,saved,impressions,reach,shares"
        url = f"{GRAPH_BASE}/{ig_media_id}/insights"
        params = {
            "metric": metrics,
            "access_token": self.token,
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            self._raise_for_graph_error(resp)
            raw = resp.json().get("data", [])
            return {item["name"]: item["values"][0]["value"] for item in raw}
        except Exception as e:
            logger.warning("Insights fetch failed for %s: %s. Falling back to basic.", ig_media_id, e)
            return self._get_basic_metrics(ig_media_id)

    def _get_basic_metrics(self, ig_media_id: str) -> Dict:
        """Fallback: fetch basic like/comment counts from media endpoint."""
        url = f"{GRAPH_BASE}/{ig_media_id}"
        params = {
            "fields": "like_count,comments_count",
            "access_token": self.token,
        }
        resp = requests.get(url, params=params, timeout=15)
        self._raise_for_graph_error(resp)
        data = resp.json()
        return {
            "like_count": data.get("like_count", 0),
            "comments_count": data.get("comments_count", 0),
            "saved": 0,
            "impressions": 0,
            "reach": 0,
            "shares": 0,
        }

    def get_account_info(self, ig_user_id: str) -> Dict:
        """Fetch basic account metadata."""
        url = f"{GRAPH_BASE}/{ig_user_id}"
        params = {
            "fields": "name,username,followers_count,media_count",
            "access_token": self.token,
        }
        resp = requests.get(url, params=params, timeout=15)
        self._raise_for_graph_error(resp)
        return resp.json()

    # ═══════════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_caption(caption: str, hashtags: List[str]) -> str:
        tag_string = " ".join(hashtags[:30])
        return f"{caption}\n\n.\n.\n.\n{tag_string}"

    @staticmethod
    def _raise_for_graph_error(response: requests.Response) -> None:
        """Raise a descriptive error for Graph API failures."""
        try:
            response.raise_for_status()
        except requests.HTTPError:
            try:
                error_data = response.json().get("error", {})
                msg = error_data.get("message", response.text)
                code = error_data.get("code", response.status_code)
                raise RuntimeError(f"Instagram Graph API error {code}: {msg}")
            except ValueError:
                raise RuntimeError(f"Instagram Graph API HTTP {response.status_code}: {response.text[:200]}")
