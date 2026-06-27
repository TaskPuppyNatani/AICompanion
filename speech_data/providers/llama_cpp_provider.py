from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import LLAMA_CPP_COMPLETION_URL, LLAMA_CPP_REQUEST_TIMEOUT_SEC


class LlamaCppProvider:
    """Provider for an externally managed llama.cpp llama-server."""

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
