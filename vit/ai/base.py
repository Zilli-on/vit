"""Provider-agnostic AI interface used by vit's merge/commit features.

Any new provider implements `AIProvider` and returns `AIResponse`.
Providers MUST fail gracefully — return None or an error string, never raise
past the caller if the user's network / service is down. Callers treat
provider absence as a signal to fall back, not a hard error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class AIResponse:
    """Normalized response from any provider.

    `text` is the raw model output (usually JSON, sometimes plain prose).
    `ok` is False if the provider couldn't be reached or refused.
    `provider` records which backend handled the call — useful for telemetry
    and for the UI to say "resolved by ollama/qwen2.5:3b".
    """

    text: str
    ok: bool
    provider: str
    error: Optional[str] = None


class AIProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        """Fast, offline-safe probe. No API call."""
        ...

    def complete(
        self, system: str, user: str, *, json_mode: bool = False
    ) -> AIResponse:
        """Run a single completion.

        `system` is the system prompt (rules + schema).
        `user` is the per-call prompt (the actual merge data).
        `json_mode` asks providers that support it to enforce valid JSON.
        Callers must still be robust to non-JSON replies.
        """
        ...
