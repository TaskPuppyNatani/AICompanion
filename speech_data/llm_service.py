"""Server-side LLM service placeholder for future local model integration.

This module defines a single integration point for future AI response generation
inside the speech server layer. The implementation is intentionally inert for
now and returns no generated text.
"""

from __future__ import annotations

from typing import Any


class LLMService:
    """Placeholder service for future server-side LLM integration.

    The speech server will eventually call this service to request model-based
    responses. Until model integration is added, every generation method returns
    ``None`` to preserve current deterministic behavior.
    """

    def build_context(
        self,
        personality: str = "",
        latest_note: str = "",
        click_count: int = 0,
        notification: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build a structured context object for future prompt construction.

        The returned structure is stable and intentionally simple so future
        model integrations can consume the same context contract.
        """
        notification_payload = notification or {}

        return {
            "personality": str(personality or ""),
            "latest_note": str(latest_note or ""),
            "click_count": int(click_count or 0),
            "notification": {
                "source": str(notification_payload.get("source", "") or ""),
                "sender": str(notification_payload.get("sender", "") or ""),
                "summary": str(notification_payload.get("summary", "") or ""),
            },
        }

    def generate_click_response(self, context: dict[str, Any]) -> str | None:
        """Future click-response generation hook.

        Returns ``None`` until a local model backend is integrated.
        """
        _ = context
        return None

    def generate_memory_response(self, context: dict[str, Any]) -> str | None:
        """Future memory-aware response generation hook.

        Returns ``None`` until a local model backend is integrated.
        """
        _ = context
        return None

    def generate_notification_response(self, context: dict[str, Any]) -> str | None:
        """Future notification-specific response generation hook.

        Returns ``None`` until a local model backend is integrated.
        """
        _ = context
        return None

    def generate_chat_response(
        self,
        context: dict[str, Any],
        event: str = "click",
    ) -> str | None:
        """Future top-level chat response generation hook.

        This method is intended to orchestrate response selection across events
        and delegate to specialized generation methods when model support is
        added. Returns ``None`` for now.
        """
        _ = (context, event)
        return None
