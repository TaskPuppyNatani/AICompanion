from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from companion_app.model_profiles import get_active_model_name
from config import (
    OLLAMA_GENERATE_URL,
    OLLAMA_HEALTH_URL,
    OLLAMA_REQUEST_TIMEOUT_SEC,
)
from speech_data.providers.base import LLMProvider


OLLAMA_FALLBACK_EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"


class OllamaProvider(LLMProvider):
    """Provider for an Ollama generate API backend."""

    def __init__(self):
        super().__init__()
        self.process = None

    def health_check(self) -> bool:
        try:
            with urlopen(OLLAMA_HEALTH_URL, timeout=1.0) as response:
                return getattr(response, "status", 200) == 200
        except (OSError, URLError):
            return False

    def _find_ollama_exe(self):
        found = shutil.which("ollama")
        if found:
            return Path(found)

        if OLLAMA_FALLBACK_EXE.is_file():
            return OLLAMA_FALLBACK_EXE

        return None

    def start(self) -> None:
        exe = self._find_ollama_exe()
        if exe is None:
            raise RuntimeError("ollama executable not found on PATH or fallback location")

        command = [str(exe), "serve"]

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
        """Ollama shutdown is intentionally not managed yet."""
        return

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
