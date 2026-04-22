"""Claude CLI provider — shells out to `claude` binary.

Zero additional cost for users who already have Claude Code installed.
Invoked via `claude --print <prompt>`, which uses their existing session
credentials. No ANTHROPIC_API_KEY needed.

Trade-offs: slower than a direct API call (CLI startup + auth), but free
for Claude Code subscribers and requires no extra dependency.
"""

from __future__ import annotations

import shutil
import subprocess

from .base import AIProvider, AIResponse


class ClaudeCliProvider:
    name = "claude_cli"

    def __init__(self, binary: str | None = None):
        self.binary = binary or shutil.which("claude")

    def is_available(self) -> bool:
        return self.binary is not None and shutil.which(self.binary) is not None

    def complete(
        self, system: str, user: str, *, json_mode: bool = False
    ) -> AIResponse:
        if not self.binary:
            return AIResponse(
                text="", ok=False, provider=self.name, error="claude not in PATH"
            )
        prompt = system.strip() + "\n\n" + user.strip()
        if json_mode:
            prompt += "\n\nReturn ONLY valid JSON — no prose, no markdown fence."
        try:
            result = subprocess.run(
                [self.binary, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=180,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            return AIResponse(text="", ok=False, provider=self.name, error=str(e))
        if result.returncode != 0:
            return AIResponse(
                text="",
                ok=False,
                provider=self.name,
                error=result.stderr.strip() or "non-zero exit",
            )
        return AIResponse(text=result.stdout.strip(), ok=True, provider=self.name)


# Protocol check.
_: AIProvider = ClaudeCliProvider()
