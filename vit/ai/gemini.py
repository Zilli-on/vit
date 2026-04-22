"""Gemini provider — wraps google-generativeai.

Optional dependency. If the SDK isn't installed or GEMINI_API_KEY is
unset, `is_available()` returns False and the factory falls through.
"""

from __future__ import annotations

import os

from .base import AIProvider, AIResponse


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str | None = None):
        self.model_name = (
            model or os.environ.get("VIT_GEMINI_MODEL") or "gemini-2.5-flash"
        )
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            return None
        try:
            import google.generativeai as genai

            genai.configure(api_key=key)
            self._client = genai.GenerativeModel(self.model_name)
            return self._client
        except Exception:
            return None

    def is_available(self) -> bool:
        if not os.environ.get("GEMINI_API_KEY"):
            return False
        try:
            import google.generativeai  # noqa: F401

            return True
        except ImportError:
            return False

    def complete(
        self, system: str, user: str, *, json_mode: bool = False
    ) -> AIResponse:
        client = self._ensure_client()
        if client is None:
            return AIResponse(text="", ok=False, provider=self.name, error="no client")
        prompt = system + "\n\n" + user
        try:
            kwargs = {}
            if json_mode:
                kwargs["generation_config"] = {"response_mime_type": "application/json"}
            resp = client.generate_content(prompt, **kwargs)
            text = getattr(resp, "text", "") or ""
        except Exception as e:
            return AIResponse(text="", ok=False, provider=self.name, error=str(e))
        return AIResponse(
            text=text,
            ok=bool(text),
            provider=f"{self.name}/{self.model_name}",
            error=None if text else "empty response",
        )


# Protocol check.
_: AIProvider = GeminiProvider()
