"""Server-side LLM service for provider-backed text generation.

This module keeps prompt construction in one place and routes generation through
the active provider selected by the provider factory.
"""

from __future__ import annotations

import re
import time
from typing import Any

from speech_data.provider_factory import get_active_provider


class LLMService:
    """Build prompts and request responses from the active LLM provider."""

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

    def generate_provider_response(
        self,
        messages: list[dict[str, str]],
        generation_options: dict[str, Any] | None = None,
    ) -> str | None:
        """Send provider-neutral messages to the active provider."""
        provider = get_active_provider()
        return provider.generate_text(messages, generation_options=generation_options)

    def is_plain_click_response(self, text: str | None) -> bool:
        """Return whether text is acceptable for an AI click bubble."""
        if not text or not text.strip():
            return False

        candidate = text.strip()
        lines = [line.strip() for line in candidate.splitlines() if line.strip()]
        if len(lines) != 1:
            return False

        line = lines[0]
        lowered = line.lower()

        if "`" in line or "```" in line:
            return False

        if line.startswith(("-", "*", "#", ">")):
            return False

        if re.match(r"^(rivet|assistant|response|reply)\s*:", lowered):
            return False

        code_patterns = (
            r"\bdef\s+\w+\s*\(",
            r"\bclass\s+\w+",
            r"\breturn\b",
            r"\bimport\b",
            r"\bfrom\s+\S+\s+import\b",
            r"\bprint\s*\(",
        )
        if any(re.search(pattern, lowered) for pattern in code_patterns):
            return False

        if "{" in line or "}" in line or '"""' in line:
            return False

        return True

    def generate_click_response(self, context: dict[str, Any]) -> str | None:
        """Generate a click response via the active provider."""
        start_time = time.perf_counter()
        try:
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

            system_message = (
                "You are Rivet, a friendly and playful AI companion.\n"
                "Use the personality profile below to stay in character.\n\n"
                "Personality profile:\n"
                f"{personality or 'No personality profile provided.'}\n\n"
                "Response rules:\n"
                "- Return exactly one sentence.\n"
                "- Keep it concise.\n"
                "- Stay in-character as Rivet.\n"
                "- Keep tone friendly and playful.\n"
                "- Plain conversational dialogue only.\n"
                "- Do not write code, examples, function definitions, labels, explanations, Markdown, or code fences.\n"
                "- Do not wrap the response in quotes.\n"
                "Return only one short spoken line from Rivet."
            )
            user_message = (
                "Current click context:\n"
                f"Click count: {click_count}\n"
                f"{latest_note_line}\n\n"
                "Memory guidance:\n"
                "- Memories are background context.\n"
                "- Do not assume the user is currently thinking about a memory.\n"
                "- Mention memories only when naturally relevant.\n"
                "- Most responses should not mention memories."
            )
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ]

            response = self.generate_provider_response(
                messages,
                generation_options={"n_predict": 32},
            )
            if not self.is_plain_click_response(response):
                return None
            return response.strip()
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            print(f"[AI CLICK PERF] llm_service.generate_click_response {elapsed_ms:.2f} ms")

    def generate_prompt_response(
        self,
        user_prompt: str,
        context: dict[str, Any],
    ) -> str | None:
        """Generate a response to an explicit user prompt."""
        try:
            personality = str(context.get("personality", "") or "").strip()
            prompt_text = str(user_prompt or "").strip()
        except (AttributeError, TypeError, ValueError):
            return None

        if not prompt_text:
            return None

        system_message = (
            "You are Rivet, a friendly and helpful AI companion.\n"
            "Use the personality profile below to stay in character.\n\n"
            "Personality profile:\n"
            f"{personality or 'No personality profile provided.'}\n\n"
            "Respond directly and naturally as Rivet."
        )
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt_text},
        ]

        response = self.generate_provider_response(messages)
        if not response or not response.strip():
            return None
        return response.strip()

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
