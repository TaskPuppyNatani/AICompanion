from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """Lightweight contract for text generation backends."""

    def generate_text(self, prompt: str) -> str | None:
        """Generate a non-streaming response for the prompt."""
        ...
