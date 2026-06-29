from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    OLLAMA_MODEL_NAME,
    OLLAMA_GENERATE_URL,
    OLLAMA_HEALTH_URL,
    OLLAMA_REQUEST_TIMEOUT_SEC,
)
from speech_data.profile_manager import get_active_profile
from speech_data.providers.base import LLMProvider


OLLAMA_FALLBACK_EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"


class OllamaProvider(LLMProvider):
    """Provider for an Ollama generate API backend."""

    def __init__(self, profile: dict[str, Any] | None = None):
        super().__init__()
        self.profile = profile or get_active_profile()
        self.apply_profile_lifecycle_settings(self.profile)
        self.process = None

    def health_check(self) -> bool:
        try:
            with urlopen(OLLAMA_HEALTH_URL, timeout=1.0) as response:
                status = getattr(response, "status", 200)
                if status == 200:
                    self.last_readiness_state = "HTTP 200 OK"
                    return True

                self.last_readiness_state = f"HTTP {status}"
                return False
        except HTTPError as e:
            preview = e.read(300).decode("utf-8", errors="replace").strip()
            self.last_readiness_state = f"HTTP {e.code}: {preview}"
            return False
        except TimeoutError:
            self.last_readiness_state = "health probe timed out"
            return False
        except (ConnectionRefusedError, ConnectionResetError):
            self.last_readiness_state = "connection refused"
            return False
        except URLError as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, TimeoutError):
                self.last_readiness_state = "health probe timed out"
            elif isinstance(reason, (ConnectionRefusedError, ConnectionResetError)):
                self.last_readiness_state = "connection refused"
            else:
                self.last_readiness_state = (
                    f"URL error: {type(reason).__name__}: {reason}"
                )
            return False
        except socket.timeout:
            self.last_readiness_state = "health probe timed out"
            return False
        except OSError as e:
            self.last_readiness_state = f"OS error: {type(e).__name__}: {e}"
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
        if not self.started_by_companion or self.process is None:
            return

        try:
            if self.process.poll() is None:
                self.process.terminate()

                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
        finally:
            self.process = None
            self.started_by_companion = False

    def generate_text(
        self,
        messages: list[dict[str, Any]] | str,
        generation_options: dict[str, Any] | None = None,
    ) -> str | None:
        start_time = time.perf_counter()
        try:
            _ = generation_options

            prompt = self.render_messages_as_prompt(messages)

            if not prompt:
                return None

            model_name = self.profile.get("model", "")

            if not isinstance(model_name, str) or not model_name.strip():
                model_name = OLLAMA_MODEL_NAME

            payload = {
                "model": model_name.strip(),
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
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            print(f"[AI CLICK PERF] ollama.generate_text {elapsed_ms:.2f} ms")
