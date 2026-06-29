from __future__ import annotations

from typing import Any


class BaseTool:
    """Minimal contract for provider-independent interaction tools."""

    def try_handle(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        raise NotImplementedError
