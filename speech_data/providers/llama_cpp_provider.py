from __future__ import annotations

import json
import subprocess
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import (
    LLAMA_CPP_COMPLETION_URL,
    LLAMA_CPP_DEFAULT_MODEL,
    LLAMA_CPP_HEALTH_URL,
    LLAMA_CPP_HOST,
    LLAMA_CPP_MODELS_DIR,
    LLAMA_CPP_PORT,
    LLAMA_CPP_REQUEST_TIMEOUT_SEC,
    LLAMA_CPP_SERVER_EXE_PATH,
)
from speech_data.providers.base import LLMProvider


class LlamaCppProvider(LLMProvider):
    """Provider for a local llama.cpp llama-server backend."""

    def __init__(self):
        super().__init__()
        self.process = None

    def health_check(self) -> bool:
        try:
            with urlopen(LLAMA_CPP_HEALTH_URL, timeout=1.0) as response:
                return getattr(response, "status", 200) == 200
        except (OSError, URLError):
            return False

    def start(self) -> None:
        model_path = LLAMA_CPP_MODELS_DIR / LLAMA_CPP_DEFAULT_MODEL

        if not LLAMA_CPP_SERVER_EXE_PATH.is_file():
            raise RuntimeError(
                f"llama-server executable not found: {LLAMA_CPP_SERVER_EXE_PATH}"
            )

        if not LLAMA_CPP_MODELS_DIR.is_dir():
            raise RuntimeError(
                f"llama.cpp models directory not found: {LLAMA_CPP_MODELS_DIR}"
            )

        if not model_path.is_file():
            raise RuntimeError(
                f"llama.cpp model not found: {model_path}"
            )

        command = [
            str(LLAMA_CPP_SERVER_EXE_PATH),
            "-m",
            str(model_path),
            "--host",
            LLAMA_CPP_HOST,
            "--port",
            str(LLAMA_CPP_PORT),
        ]

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            raise RuntimeError(f"Launch failed for command {command}: {e}") from e

        self.started_by_companion = True

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
