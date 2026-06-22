from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from companion_app.model_profiles import get_active_model_name
from config import OLLAMA_GENERATE_URL, OLLAMA_REQUEST_TIMEOUT_SEC


class OllamaProvider:
    """Current production provider using Ollama generate API."""

    def generate_text(self, prompt: str) -> str | None:
        if not isinstance(prompt, str) or not prompt.strip():
            return None

        model_name = get_active_model_name()

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        }

        request = Request(
            OLLAMA_GENERATE_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=OLLAMA_REQUEST_TIMEOUT_SEC) as response:
                if getattr(response, "status", 200) >= 400:
                    return None

                response_data = response.read().decode("utf-8")

            parsed = json.loads(response_data)

        except (OSError, URLError, ValueError, TypeError) as e:
            print("OLLAMA FAILED:", repr(e))
            return None

        generated_text = parsed.get("response")

        if not isinstance(generated_text, str):
            return None

        generated_text = generated_text.strip()
        return generated_text or None
