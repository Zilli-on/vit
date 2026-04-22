"""Pluggable AI provider layer for Vit.

Providers:
  - ollama       local-first, zero-cost, default when reachable
  - gemini       Gemini API (google-generativeai); free tier, optional
  - claude_cli   shells out to `claude` CLI; zero cost for Claude Code users
  - heuristic    pure-Python fallback, always available, no network

Provider selection order (first reachable wins):
  explicit VIT_AI_PROVIDER env / config
  -> ollama (if 127.0.0.1:11434 open)
  -> gemini (if GEMINI_API_KEY set)
  -> claude_cli (if `claude` in PATH)
  -> heuristic

All providers implement the AIProvider protocol in base.py.
"""

from .base import AIProvider, AIResponse
from .factory import get_provider

__all__ = ["AIProvider", "AIResponse", "get_provider"]
