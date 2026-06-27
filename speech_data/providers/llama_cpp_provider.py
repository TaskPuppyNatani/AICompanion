from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import (
    LLAMA_CPP_COMPLETION_URL,
    LLAMA_CPP_HEALTH_URL,
    LLAMA_CPP_REQUEST_TIMEOUT_SEC,
)
from speech_data.providers.base import LLMProvider


class LlamaCppProvider(LLMProvider):
    """Provider for an externally managed llama.cpp llama-server."""

    def health_check(self) -> bool:
        try:
            with urlopen(LLAMA_CPP_HEALTH_URL, timeout=1.0) as response:
                return getattr(response, "status", 200) == 200
        except (OSError, URLError):
            return False

    def start(self) -> None:
        """llama-server is externally managed for now."""
        return

    def stop(self) -> None:
        """llama-server shutdown is intentionally not managed yet."""
        return

    def generate_text(self, prompt: str) -> str | None:
        if not isinstance(prompt, str) or not prompt.strip():
            return None

        payload = {
            "prompt": prompt,
            "stream": False,
        }

        request = Request(
            LLAMA_CPP_COMPLETION_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=LLAMA_CPP_REQUEST_TIMEOUT_SEC) as response:
                if getattr(response, "status", 200) >= 400:
                    return None

                response_data = response.read().decode("utf-8")

            parsed = json.loads(response_data)

        except (OSError, URLError, ValueError, TypeError) as e:
            print("LLAMA.CPP FAILED:", repr(e))
            return None

        generated_text = parsed.get("content")

        if not isinstance(generated_text, str):
            return None

        generated_text = generated_text.strip()
        return generated_text or None
