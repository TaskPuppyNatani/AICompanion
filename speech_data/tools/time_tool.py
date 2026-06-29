from __future__ import annotations

from datetime import datetime
from typing import Any

from speech_data.tools.base import BaseTool


class TimeTool(BaseTool):
    """Answer simple local-time requests without invoking an LLM provider."""

    TIME_REQUESTS = {
        "what time is it",
        "what time is it?",
        "current time",
        "tell me the time",
        "tell me the time.",
        "time",
    }

    def try_handle(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        _ = context
        normalized_text = " ".join(str(text or "").lower().strip().split())

        if normalized_text not in self.TIME_REQUESTS:
            return None

        current_time = datetime.now().strftime("%I:%M %p").lstrip("0")
        return f"It's {current_time}."
