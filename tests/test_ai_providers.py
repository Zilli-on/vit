"""Unit tests for vit.ai providers + factory.

No network calls. Ollama HTTP is mocked via urllib.request.urlopen; the
socket-probe is mocked via socket.create_connection.
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch


from vit.ai import get_provider
from vit.ai.claude_cli import ClaudeCliProvider
from vit.ai.factory import _PROVIDERS, _config_provider
from vit.ai.gemini import GeminiProvider
from vit.ai.heuristic import HeuristicProvider
from vit.ai.ollama import OllamaProvider


# --- HeuristicProvider -------------------------------------------------------


def test_heuristic_is_always_available():
    assert HeuristicProvider().is_available() is True


def test_heuristic_returns_empty_envelope():
    r = HeuristicProvider().complete("sys", "user")
    assert r.ok is True
    assert r.provider == "heuristic"
    data = json.loads(r.text)
    assert data["decisions"] == []


# --- OllamaProvider ----------------------------------------------------------


def test_ollama_is_available_when_socket_opens():
    p = OllamaProvider()
    with patch("socket.create_connection") as conn:
        conn.return_value.__enter__ = lambda self: self
        conn.return_value.__exit__ = lambda *a: None
        assert p.is_available() is True


def test_ollama_is_not_available_when_socket_closed():
    p = OllamaProvider()
    with patch("socket.create_connection", side_effect=OSError("refused")):
        assert p.is_available() is False


def _fake_urlopen_response(body: dict):
    buf = io.BytesIO(json.dumps(body).encode("utf-8"))
    buf.__enter__ = lambda self: self  # type: ignore[method-assign]
    buf.__exit__ = lambda *a: None  # type: ignore[method-assign]
    return buf


def test_ollama_complete_parses_chat_response():
    p = OllamaProvider(model="qwen2.5:3b")
    body = {"message": {"role": "assistant", "content": "hello"}}
    with patch("urllib.request.urlopen", return_value=_fake_urlopen_response(body)):
        r = p.complete("sys", "user")
    assert r.ok is True
    assert r.text == "hello"
    assert r.provider == "ollama/qwen2.5:3b"


def test_ollama_complete_handles_network_error():
    p = OllamaProvider()
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("boom"),
    ):
        r = p.complete("sys", "user")
    assert r.ok is False
    assert "boom" in (r.error or "")


def test_ollama_complete_handles_empty_response():
    p = OllamaProvider()
    with patch(
        "urllib.request.urlopen",
        return_value=_fake_urlopen_response({"message": {"content": ""}}),
    ):
        r = p.complete("sys", "user")
    assert r.ok is False
    assert r.error == "empty response"


def test_ollama_honors_env_model(monkeypatch):
    monkeypatch.setenv("VIT_OLLAMA_MODEL", "llama3.1:8b")
    assert OllamaProvider().model == "llama3.1:8b"


# --- GeminiProvider ----------------------------------------------------------


def test_gemini_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert GeminiProvider().is_available() is False


def test_gemini_complete_returns_error_without_client(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = GeminiProvider().complete("sys", "user")
    assert r.ok is False


# --- ClaudeCliProvider -------------------------------------------------------


def test_claude_cli_unavailable_without_binary():
    with patch("shutil.which", return_value=None):
        assert ClaudeCliProvider().is_available() is False


def test_claude_cli_complete_returns_stdout():
    p = ClaudeCliProvider(binary="/fake/claude")
    fake = MagicMock(returncode=0, stdout="answer\n", stderr="")
    with (
        patch("shutil.which", return_value="/fake/claude"),
        patch("subprocess.run", return_value=fake),
    ):
        r = p.complete("sys", "user")
    assert r.ok is True
    assert r.text == "answer"


def test_claude_cli_complete_reports_nonzero_exit():
    p = ClaudeCliProvider(binary="/fake/claude")
    fake = MagicMock(returncode=1, stdout="", stderr="nope")
    with (
        patch("shutil.which", return_value="/fake/claude"),
        patch("subprocess.run", return_value=fake),
    ):
        r = p.complete("sys", "user")
    assert r.ok is False
    assert "nope" in (r.error or "")


# --- Factory ----------------------------------------------------------------


def test_factory_falls_through_to_heuristic(monkeypatch):
    """If every real provider reports unavailable, heuristic wins."""
    monkeypatch.delenv("VIT_AI_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with (
        patch.object(OllamaProvider, "is_available", return_value=False),
        patch.object(ClaudeCliProvider, "is_available", return_value=False),
        patch.object(GeminiProvider, "is_available", return_value=False),
    ):
        p = get_provider(project_dir=None)
    assert p.name == "heuristic"


def test_factory_prefers_ollama_when_available(monkeypatch):
    monkeypatch.delenv("VIT_AI_PROVIDER", raising=False)
    with patch.object(OllamaProvider, "is_available", return_value=True):
        p = get_provider(project_dir=None)
    assert p.name == "ollama"


def test_factory_honors_env_override(monkeypatch):
    monkeypatch.setenv("VIT_AI_PROVIDER", "heuristic")
    with patch.object(OllamaProvider, "is_available", return_value=True):
        p = get_provider(project_dir=None)
    assert p.name == "heuristic"


def test_factory_ignores_unknown_env(monkeypatch):
    monkeypatch.setenv("VIT_AI_PROVIDER", "i-do-not-exist")
    with patch.object(OllamaProvider, "is_available", return_value=True):
        p = get_provider(project_dir=None)
    assert p.name == "ollama"


def test_factory_reads_project_config(tmp_path, monkeypatch):
    monkeypatch.delenv("VIT_AI_PROVIDER", raising=False)
    vit_dir = tmp_path / ".vit"
    vit_dir.mkdir()
    (vit_dir / "config.json").write_text(json.dumps({"ai": {"provider": "heuristic"}}))
    with patch.object(OllamaProvider, "is_available", return_value=True):
        p = get_provider(project_dir=str(tmp_path))
    assert p.name == "heuristic"


def test_config_provider_handles_missing_file(tmp_path):
    assert _config_provider(str(tmp_path)) is None


def test_config_provider_handles_corrupt_json(tmp_path):
    (tmp_path / ".vit").mkdir()
    (tmp_path / ".vit" / "config.json").write_text("{ not json")
    assert _config_provider(str(tmp_path)) is None


def test_all_providers_satisfy_protocol():
    """Each registered provider must expose name + is_available + complete."""
    for name, cls in _PROVIDERS.items():
        inst = cls()
        assert hasattr(inst, "name"), name
        assert callable(getattr(inst, "is_available", None)), name
        assert callable(getattr(inst, "complete", None)), name
