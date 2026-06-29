from __future__ import annotations

import json
import socket
import subprocess
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    LLAMA_CPP_CHAT_COMPLETIONS_URL,
    LLAMA_CPP_COMPLETION_URL,
    LLAMA_CPP_HEALTH_URL,
    LLAMA_CPP_HOST,
    LLAMA_CPP_PORT,
    LLAMA_CPP_REQUEST_TIMEOUT_SEC,
    LLAMA_CPP_SERVER_EXE_PATH,
)
from speech_data.profile_manager import (
    get_active_profile,
    resolve_model_path,
    resolve_optional_profile_path,
)
from speech_data.providers.base import LLMProvider


class LlamaCppProvider(LLMProvider):
    """Provider for a local llama.cpp llama-server backend."""

    def __init__(self, profile: dict[str, Any] | None = None):
        super().__init__()
        self.profile = profile or get_active_profile()
        self.apply_profile_lifecycle_settings(self.profile)
        self.process = None

    def health_check(self) -> bool:
        try:
            with urlopen(LLAMA_CPP_HEALTH_URL, timeout=1.0) as response:
                status = getattr(response, "status", 200)
                if status == 200:
                    self.last_readiness_state = "HTTP 200 OK"
                    return True

                self.last_readiness_state = f"HTTP {status}"
                return False
        except HTTPError as e:
            preview = e.read(300).decode("utf-8", errors="replace").strip()
            if e.code == 503:
                self.last_readiness_state = f"HTTP 503 loading: {preview}"
            else:
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

    def start(self) -> None:
        model_path = resolve_model_path(self.profile)
        mmproj_path = resolve_optional_profile_path(self.profile, "mmproj")

        if not LLAMA_CPP_SERVER_EXE_PATH.is_file():
            raise RuntimeError(
                f"llama-server executable not found: {LLAMA_CPP_SERVER_EXE_PATH}"
            )

        if not model_path.is_file():
            raise RuntimeError(
                f"llama.cpp model not found: {model_path}"
            )

        if mmproj_path is not None and not mmproj_path.is_file():
            raise RuntimeError(
                f"llama.cpp multimodal projector not found: {mmproj_path}"
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

        if mmproj_path is not None:
            command.extend(["--mmproj", str(mmproj_path)])

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

    def supports_image_input(self) -> bool:
        category = self.profile.get("category")

        if isinstance(category, str) and category.strip().lower() == "vision":
            return True

        mmproj = self.profile.get("mmproj")
        return isinstance(mmproj, str) and bool(mmproj.strip())

    def build_chat_completion_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        chat_messages: list[dict[str, Any]] = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if not isinstance(content, list):
                chat_messages.append({
                    "role": role,
                    "content": content,
                })
                continue

            content_parts: list[dict[str, Any]] = []

            for part in content:
                if not isinstance(part, dict):
                    continue

                if part.get("type") == "text":
                    text = part.get("text")

                    if isinstance(text, str) and text.strip():
                        content_parts.append({
                            "type": "text",
                            "text": text.strip(),
                        })

                elif part.get("type") == "image":
                    mime_type = part.get("mime_type")
                    data_base64 = part.get("data_base64")

                    if (
                        isinstance(mime_type, str)
                        and mime_type.strip()
                        and isinstance(data_base64, str)
                        and data_base64.strip()
                    ):
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:{mime_type.strip()};"
                                    f"base64,{data_base64.strip()}"
                                ),
                            },
                        })

            if content_parts:
                chat_messages.append({
                    "role": role,
                    "content": content_parts,
                })

        return chat_messages

    def generate_text(
        self,
        messages: list[dict[str, Any]] | str,
        generation_options: dict[str, Any] | None = None,
    ) -> str | None:
        start_time = time.perf_counter()
        try:
            normalized_messages = self.normalize_messages(messages)

            if not normalized_messages:
                return None

            prompt_format = self.profile.get("prompt_format", "completion")
            has_image = self.messages_include_image(normalized_messages)

            if has_image and (prompt_format != "chat" or not self.supports_image_input()):
                print("LLAMA.CPP FAILED: image input is not supported by this profile")
                return None

            if prompt_format == "chat":
                chat_messages = self.build_chat_completion_messages(normalized_messages)

                if not chat_messages:
                    return None

                payload = {
                    "messages": chat_messages,
                    "stream": False,
                }
                request_url = LLAMA_CPP_CHAT_COMPLETIONS_URL
            else:
                prompt = self.render_messages_as_prompt(normalized_messages)

                if not prompt:
                    return None

                payload = {
                    "prompt": prompt,
                    "stream": False,
                }
                request_url = LLAMA_CPP_COMPLETION_URL

            if isinstance(generation_options, dict):
                n_predict = generation_options.get("n_predict")

                if (
                    isinstance(n_predict, int)
                    and not isinstance(n_predict, bool)
                    and n_predict > 0
                ):
                    if prompt_format == "chat":
                        payload["max_tokens"] = n_predict
                    else:
                        payload["n_predict"] = n_predict

            request = Request(
                request_url,
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

            if prompt_format == "chat":
                choices = parsed.get("choices")
                generated_text = None

                if isinstance(choices, list) and choices:
                    first_choice = choices[0]

                    if isinstance(first_choice, dict):
                        message = first_choice.get("message")

                        if isinstance(message, dict):
                            generated_text = message.get("content")
            else:
                generated_text = parsed.get("content")

            if not isinstance(generated_text, str):
                return None

            generated_text = generated_text.strip()
            return generated_text or None
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            print(f"[AI CLICK PERF] llama_cpp.generate_text {elapsed_ms:.2f} ms")
