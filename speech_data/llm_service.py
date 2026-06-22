"""Server-side LLM service placeholder for future local model integration.

This module defines a single integration point for future AI response generation
inside the speech server layer. The implementation is intentionally inert for
now and returns no generated text.
"""

from __future__ import annotations

from typing import Any
from speech_data.provider_factory import get_active_provider


#OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
#OLLAMA_MODEL_NAME = "phi4-mini:latest"


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

    def generate_ollama_response(self, prompt: str) -> str | None:
        """Send a minimal prompt request to Ollama and return generated text.

        This helper is intentionally not wired into existing response methods,
        so current fallback behavior remains unchanged.
        """
        provider = get_active_provider()
        return provider.generate_text(prompt)

    def generate_click_response(self, context: dict[str, Any]) -> str | None:
        """Generate an experimental click response via Ollama."""
        try:
            personality = str(context.get("personality", "") or "").strip()
            click_count = int(context.get("click_count", 0) or 0)
            latest_note = str(context.get("latest_note", "") or "").strip()
        except (AttributeError, TypeError, ValueError):
            return None

        if latest_note:
            latest_note_line = f"Latest note: {latest_note}"
        else:
            latest_note_line = "Latest note: none"

        prompt = (
            "You are Rivet, a friendly and playful AI companion.\n"
            "Use the personality profile below to stay in character.\n\n"
            "Personality profile:\n"
            f"{personality or 'No personality profile provided.'}\n\n"
            "Current click context:\n"
            f"Click count: {click_count}\n"
            f"{latest_note_line}\n\n"
            "Memory guidance:\n"
            "- Memories are background context.\n"
            "- Do not assume the user is currently thinking about a memory.\n"
            "- Mention memories only when naturally relevant.\n"
            "- Most responses should not mention memories.\n\n"
            "Response rules:\n"
            "- Return exactly one sentence.\n"
            "- Keep it concise.\n"
            "- Stay in-character as Rivet.\n"
            "- Keep tone friendly and playful.\n"
            "- No roleplay formatting.\n"
            "- No markdown.\n"
            "Return only the response sentence."
        )

        return self.generate_ollama_response(prompt)

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
