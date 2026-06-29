from __future__ import annotations

from typing import Any


class IntentRouter:
    """Deterministic profile router for prompt interactions."""

    CODING_KEYWORDS = {
        "python",
        "code",
        "coding",
        "bug",
        "traceback",
        "compile",
        "function",
        "class",
        "method",
        "variable",
        "git",
        "terminal",
        "regex",
    }
    REASONING_KEYWORDS = {
        "explain",
        "analyze",
        "compare",
        "why",
        "reason",
        "optimize",
        "algorithm",
        "architecture",
        "design",
    }

    def route(self, text: str, context: dict[str, Any] | None = None) -> str | None:
        _ = context
        normalized_text = str(text or "").lower()

        if any(keyword in normalized_text for keyword in self.CODING_KEYWORDS):
            return "fast-coder"

        if any(keyword in normalized_text for keyword in self.REASONING_KEYWORDS):
            return "deep-think"

        return "fast-chat"
