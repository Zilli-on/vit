"""Zero-network heuristic fallback.

Used when no real AI provider is reachable. Returns predictable, shallow
responses — never pretends to do semantic merging. The caller is expected
to treat this as "no AI" and skip AI-dependent steps.
"""

from __future__ import annotations

from .base import AIProvider, AIResponse


class HeuristicProvider:
    name = "heuristic"

    def is_available(self) -> bool:
        return True

    def complete(
        self, system: str, user: str, *, json_mode: bool = False
    ) -> AIResponse:
        # Return a minimal JSON envelope the callers can parse — signals
        # "no semantic opinion; fall back to deterministic rules".
        return AIResponse(
            text='{"summary": "heuristic fallback: no AI used", "decisions": []}',
            ok=True,
            provider=self.name,
        )


# Sanity check that we satisfy the protocol.
_: AIProvider = HeuristicProvider()
