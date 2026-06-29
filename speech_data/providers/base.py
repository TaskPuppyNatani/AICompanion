from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Base contract and lifecycle orchestration for text generation backends."""

    startup_timeout_seconds = 15
    poll_interval_seconds = 0.5

    def __init__(self):
        self.started_by_companion = False
        self.last_readiness_state = "not checked"

    def apply_profile_lifecycle_settings(
        self,
        profile: dict[str, Any] | None,
    ) -> None:
        """Apply optional lifecycle settings supplied by a model profile."""
        if not isinstance(profile, dict):
            return

        startup_timeout = profile.get("startup_timeout_seconds")

        if isinstance(startup_timeout, bool):
            return

        if isinstance(startup_timeout, (int, float)) and startup_timeout > 0:
            self.startup_timeout_seconds = float(startup_timeout)

    @abstractmethod
    def health_check(self) -> bool:
        """Return whether the provider is ready to accept requests."""
        ...

    @abstractmethod
    def start(self) -> None:
        """Start the provider when supported by this backend."""
        ...

    def ensure_running(self) -> None:
        """Start the provider if needed and wait until it is healthy."""
        start_time = time.monotonic()
        provider_name = type(self).__name__

        if self.health_check():
            elapsed = time.monotonic() - start_time
            print(f"Provider ready: {provider_name} ({elapsed:.2f} s)")
            return

        print(f"Starting provider: {provider_name}")
        self.start()

        deadline = time.monotonic() + self.startup_timeout_seconds

        while time.monotonic() < deadline:
            process = getattr(self, "process", None)
            if process is not None:
                return_code = process.poll()

                if return_code is not None:
                    self.last_readiness_state = (
                        f"process exited with code {return_code}"
                    )
                    elapsed = time.monotonic() - start_time
                    print(
                        f"Provider failed: {provider_name} ({elapsed:.2f} s): "
                        f"{self.last_readiness_state}"
                    )
                    raise RuntimeError(
                        f"{type(self).__name__} failed to become ready: "
                        f"{self.last_readiness_state}"
                    )

            if self.health_check():
                elapsed = time.monotonic() - start_time
                print(f"Provider ready: {provider_name} ({elapsed:.2f} s)")
                return

            time.sleep(self.poll_interval_seconds)

        elapsed = time.monotonic() - start_time
        print(
            f"Provider failed: {provider_name} ({elapsed:.2f} s): "
            f"{self.last_readiness_state}"
        )
        raise RuntimeError(
            f"{type(self).__name__} failed to become ready: "
            f"{self.last_readiness_state}"
        )

    @abstractmethod
    def stop(self) -> None:
        """Stop the provider when supported by this backend."""
        ...

    @abstractmethod
    def generate_text(
        self,
        messages: list[dict[str, Any]] | str,
        generation_options: dict[str, Any] | None = None,
    ) -> str | None:
        """Generate a non-streaming response for the prompt."""
        ...

    def normalize_content_parts(
        self,
        content: list[Any],
    ) -> list[dict[str, Any]]:
        normalized_parts: list[dict[str, Any]] = []

        for part in content:
            if not isinstance(part, dict):
                continue

            part_type = part.get("type")

            if part_type == "text":
                text = part.get("text", "")

                if not isinstance(text, str):
                    text = str(text or "")

                text = text.strip()

                if text:
                    normalized_parts.append({
                        "type": "text",
                        "text": text,
                    })

            elif part_type == "image":
                mime_type = part.get("mime_type")
                data_base64 = part.get("data_base64")
                name = part.get("name", "image")

                if (
                    isinstance(mime_type, str)
                    and mime_type.strip()
                    and isinstance(data_base64, str)
                    and data_base64.strip()
                ):
                    normalized_parts.append({
                        "type": "image",
                        "mime_type": mime_type.strip(),
                        "data_base64": data_base64.strip(),
                        "name": name.strip() if isinstance(name, str) and name.strip() else "image",
                    })

        return normalized_parts

    def normalize_messages(
        self,
        messages: list[dict[str, Any]] | str,
    ) -> list[dict[str, Any]]:
        """Normalize provider-neutral messages into role/content dictionaries."""
        if isinstance(messages, str):
            content = messages.strip()
            return [{"role": "user", "content": content}] if content else []

        if not isinstance(messages, list):
            return []

        normalized_messages: list[dict[str, Any]] = []

        for message in messages:
            if not isinstance(message, dict):
                continue

            role = message.get("role", "user")
            content = message.get("content", "")

            if not isinstance(role, str):
                role = "user"

            role = role.strip().lower() or "user"

            if isinstance(content, list):
                content_parts = self.normalize_content_parts(content)

                if content_parts:
                    normalized_messages.append({
                        "role": role,
                        "content": content_parts,
                    })
                continue

            if not isinstance(content, str):
                content = str(content or "")

            text_content = content.strip()

            if text_content:
                normalized_messages.append({
                    "role": role,
                    "content": text_content,
                })

        return normalized_messages

    def messages_include_image(self, messages: list[dict[str, Any]] | str) -> bool:
        normalized_messages = self.normalize_messages(messages)

        for message in normalized_messages:
            content = message.get("content")

            if not isinstance(content, list):
                continue

            if any(part.get("type") == "image" for part in content if isinstance(part, dict)):
                return True

        return False

    def render_messages_as_prompt(
        self,
        messages: list[dict[str, Any]] | str,
    ) -> str:
        """Render provider-neutral messages into a raw completion prompt."""
        normalized_messages = self.normalize_messages(messages)
        prompt_parts = []

        for message in normalized_messages:
            role = message["role"]
            content = message["content"]

            if isinstance(content, list):
                text_parts = [
                    part["text"]
                    for part in content
                    if isinstance(part, dict)
                    and part.get("type") == "text"
                    and isinstance(part.get("text"), str)
                    and part.get("text").strip()
                ]
                content = "\n".join(text_parts).strip()

                if any(
                    isinstance(part, dict) and part.get("type") == "image"
                    for part in message["content"]
                ):
                    return ""

            if not isinstance(content, str) or not content.strip():
                continue

            if role == "system":
                prompt_parts.append(content)
            elif role == "assistant":
                prompt_parts.append(f"Assistant:\n{content}")
            else:
                prompt_parts.append(f"User:\n{content}")

        return "\n\n".join(prompt_parts).strip()
