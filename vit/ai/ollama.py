"""Ollama provider — local-first, zero-cost.

Talks HTTP to a local Ollama daemon at OLLAMA_HOST (default
http://127.0.0.1:11434). No SDK dependency; stdlib urllib only.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

from .base import AIProvider, AIResponse


class OllamaProvider:
    name = "ollama"

    def __init__(self, host: str | None = None, model: str | None = None):
        self.host = (
            host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
        ).rstrip("/")
        # qwen2.5:3b is the user's zero-cost default; overrideable.
        self.model = model or os.environ.get("VIT_OLLAMA_MODEL") or "qwen2.5:3b"

    def is_available(self) -> bool:
        """Cheap TCP probe — does NOT pull a model or send a completion."""
        try:
            parsed = urllib.parse.urlparse(self.host)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 11434
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            return False

    def complete(
        self, system: str, user: str, *, json_mode: bool = False
    ) -> AIResponse:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["format"] = "json"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            return AIResponse(text="", ok=False, provider=self.name, error=str(e))
        message = data.get("message", {})
        text = message.get("content", "") if isinstance(message, dict) else ""
        return AIResponse(
            text=text,
            ok=bool(text),
            provider=f"{self.name}/{self.model}",
            error=None if text else "empty response",
        )


# Protocol check.
_: AIProvider = OllamaProvider()
