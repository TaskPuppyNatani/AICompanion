from __future__ import annotations

from typing import Any

from speech_data.tools.base import BaseTool
from speech_data.tools.time_tool import TimeTool


class ToolManager:
    """Simple registry for provider-independent tools."""

    def __init__(self, tools: list[BaseTool] | None = None):
        self.tools = tools if tools is not None else [TimeTool()]

    def handle(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        for tool in self.tools:
            response = tool.try_handle(text, context=context)

            if response is not None:
                return response

        return None
