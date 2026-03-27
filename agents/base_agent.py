"""
Base agent class — shared scaffolding for every AI agent in the system.
"""
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain.schema import HumanMessage, SystemMessage

from config.settings import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class providing:
    - A configured LangChain ChatAnthropic client (Claude)
    - Retry logic with exponential back-off
    - Structured logging
    - Abstract `run()` method all agents must implement
    """

    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 2.0

    def __init__(self, agent_name: str, temperature: Optional[float] = None):
        self.name = agent_name
        self.logger = logging.getLogger(f"agent.{agent_name}")
        self.llm = ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            temperature=temperature if temperature is not None else settings.ANTHROPIC_TEMPERATURE,
            api_key=settings.ANTHROPIC_API_KEY,
        )

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Execute the agent's primary task."""
        ...

    # ─── LLM helpers ─────────────────────────────────────────────────────────

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        """Call Claude with retry logic."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.llm.invoke(messages)
                return response.content.strip()
            except Exception as exc:
                delay = self.RETRY_BASE_DELAY ** attempt
                self.logger.warning(
                    "Claude call failed (attempt %d/%d): %s. Retrying in %.1fs",
                    attempt, self.MAX_RETRIES, exc, delay,
                )
                if attempt == self.MAX_RETRIES:
                    raise
                time.sleep(delay)
        raise RuntimeError("Claude call exhausted retries")

    def _chat_json(self, system_prompt: str, user_prompt: str) -> Any:
        """
        Call Claude and parse the response as JSON.
        Tries multiple extraction strategies before raising.
        """
        raw = self._chat(system_prompt, user_prompt)
        cleaned = raw.strip()

        # Strategy 1: strip markdown fences
        if "```" in cleaned:
            parts = cleaned.split("```")
            for part in parts:
                candidate = part.lstrip("json").strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

        # Strategy 2: direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Strategy 3: scan every '[' position for a valid JSON array
        for i, ch in enumerate(cleaned):
            if ch == "[":
                # try from here to each ']' scanning backwards
                end = cleaned.rfind("]")
                while end > i:
                    try:
                        return json.loads(cleaned[i : end + 1])
                    except json.JSONDecodeError:
                        end = cleaned.rfind("]", 0, end)

        # Strategy 4: scan every '{' position for a valid JSON object
        for i, ch in enumerate(cleaned):
            if ch == "{":
                end = cleaned.rfind("}")
                while end > i:
                    try:
                        return json.loads(cleaned[i : end + 1])
                    except json.JSONDecodeError:
                        end = cleaned.rfind("}", 0, end)

        # Nothing worked — re-raise with context
        raise json.JSONDecodeError(
            f"Could not parse JSON from Claude response (len={len(raw)})",
            cleaned, 0
        )

    # ─── Utility ─────────────────────────────────────────────────────────────

    def _log_start(self, context: str = "") -> None:
        self.logger.info("[%s] Starting — %s", self.name, context or "no context")

    def _log_done(self, result_summary: str = "") -> None:
        self.logger.info("[%s] Done — %s", self.name, result_summary or "OK")

    def _log_error(self, error: Exception, context: str = "") -> None:
        self.logger.error("[%s] Error in %s: %s", self.name, context, error, exc_info=True)
