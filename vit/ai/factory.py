"""Picks an AI provider based on env + config + availability.

Order (first reachable wins):
  1. `VIT_AI_PROVIDER` env var  (explicit override)
  2. .vit/config.json `ai.provider` field  (per-project)
  3. ollama if daemon reachable
  4. gemini if GEMINI_API_KEY set
  5. claude_cli if `claude` in PATH
  6. heuristic (always)

Never raises past the caller — if everything fails, returns HeuristicProvider.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from .base import AIProvider
from .claude_cli import ClaudeCliProvider
from .gemini import GeminiProvider
from .heuristic import HeuristicProvider
from .ollama import OllamaProvider


_PROVIDERS = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "claude_cli": ClaudeCliProvider,
    "heuristic": HeuristicProvider,
}


def _config_provider(project_dir: Optional[str]) -> Optional[str]:
    if not project_dir:
        return None
    path = os.path.join(project_dir, ".vit", "config.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    ai = cfg.get("ai", {})
    return ai.get("provider") if isinstance(ai, dict) else None


def get_provider(
    project_dir: Optional[str] = None,
    *,
    override: Optional[str] = None,
) -> AIProvider:
    """Return the highest-priority available provider."""

    # 1. explicit override (CLI flag)
    if override and override in _PROVIDERS:
        prov = _PROVIDERS[override]()
        if prov.is_available():
            return prov

    # 2. env var
    env_pick = os.environ.get("VIT_AI_PROVIDER", "").strip().lower()
    if env_pick and env_pick in _PROVIDERS:
        prov = _PROVIDERS[env_pick]()
        if prov.is_available():
            return prov

    # 3. project config
    cfg_pick = _config_provider(project_dir)
    if cfg_pick and cfg_pick in _PROVIDERS:
        prov = _PROVIDERS[cfg_pick]()
        if prov.is_available():
            return prov

    # 4. auto-discovery in the preferred order
    for name in ("ollama", "gemini", "claude_cli"):
        prov = _PROVIDERS[name]()
        if prov.is_available():
            return prov

    return HeuristicProvider()
