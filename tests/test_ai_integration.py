"""Integration tests for ai_merge routed through the real provider chain.

test_ai_merge.py patches _ai_complete directly, which is fast and cheap
but hides wiring mistakes between ai_merge, the factory, and the
concrete providers. These tests mock the provider's complete() method
one layer deeper, so a renamed method or a broken import chain gets
caught here.
"""

from __future__ import annotations

import json

import pytest

from vit.ai.base import AIResponse
from vit.ai_merge import (
    MergeAnalysis,
    ai_analyze_merge,
    suggest_commit_message,
    summarize_log,
    classify_commit_type,
    analyze_branch_comparison,
)


def _response(text: str, ok: bool = True, provider: str = "test") -> AIResponse:
    return AIResponse(text=text, ok=ok, provider=provider)


@pytest.fixture
def force_heuristic(monkeypatch):
    """Make the factory return HeuristicProvider only, so other providers
    (ollama, gemini, claude_cli) can't interfere with the test."""
    from vit.ai.heuristic import HeuristicProvider

    monkeypatch.setattr(
        "vit.ai_merge.get_provider", lambda *a, **k: HeuristicProvider()
    )
    yield


@pytest.fixture
def captured_provider(monkeypatch):
    """Inject a provider whose .complete() we control + inspect."""
    captured = {"calls": []}

    class _Fake:
        name = "fake"

        def is_available(self):
            return True

        def complete(self, system, user, *, json_mode=False):
            captured["calls"].append(
                {"system": system, "user": user, "json_mode": json_mode}
            )
            return captured.get("next") or _response("")

    fake = _Fake()
    monkeypatch.setattr("vit.ai_merge.get_provider", lambda *a, **k: fake)
    captured["provider"] = fake
    yield captured


# ---------- factory wiring ----------


def test_ai_analyze_merge_asks_provider_in_json_mode(captured_provider):
    captured_provider["next"] = _response(
        json.dumps({"summary": "ok", "decisions": [], "resolved": {}})
    )
    result = ai_analyze_merge({}, {}, {}, [], [])

    assert isinstance(result, MergeAnalysis)
    assert result.summary == "ok"
    # Exactly one provider call, in json_mode.
    assert len(captured_provider["calls"]) == 1
    assert captured_provider["calls"][0]["json_mode"] is True


def test_ai_analyze_merge_returns_none_when_provider_refuses(captured_provider):
    captured_provider["next"] = _response("", ok=False)
    result = ai_analyze_merge({}, {}, {}, [], [])
    assert result is None


def test_suggest_commit_message_passes_plain_text(captured_provider):
    captured_provider["next"] = _response("Add B-roll on V2")
    msg = suggest_commit_message("  + Added clip 'B-Roll.mov'")
    assert msg == "Add B-roll on V2"
    assert captured_provider["calls"][0]["json_mode"] is False


def test_suggest_commit_message_truncates_over_72_chars(captured_provider):
    captured_provider["next"] = _response("x" * 200)
    msg = suggest_commit_message("diff")
    assert msg is not None
    assert len(msg) <= 72
    assert msg.endswith("...")


def test_suggest_commit_message_skips_provider_for_empty_diff(captured_provider):
    msg = suggest_commit_message("")
    assert msg is None
    # No provider call at all.
    assert captured_provider["calls"] == []


def test_summarize_log_strips_result(captured_provider):
    captured_provider["next"] = _response("  Two commits added B-roll.  \n")
    out = summarize_log("abc1234 commit one\ndef5678 commit two")
    assert out == "Two commits added B-roll."


def test_summarize_log_empty_returns_none_without_call(captured_provider):
    out = summarize_log("")
    assert out is None
    assert captured_provider["calls"] == []


def test_classify_commit_uses_heuristic_majority_before_provider(captured_provider):
    # 3/3 audio files -> heuristic short-circuits, provider never called.
    result = classify_commit_type(
        "abc1234",
        ["timeline/audio.json", "audio/track1.aac", "audio/track2.wav"],
        message="volume tweaks",
    )
    assert result == "audio"
    assert captured_provider["calls"] == []


def test_classify_commit_falls_back_to_provider_on_mixed_files(captured_provider):
    captured_provider["next"] = _response(
        json.dumps({"category": "color", "confidence": "high", "reasoning": "x"})
    )
    result = classify_commit_type(
        "abc1234",
        ["timeline/markers.json", "timeline/metadata.json"],
        message="polish",
    )
    assert result == "color"
    assert len(captured_provider["calls"]) == 1


def test_analyze_branch_comparison_hits_provider_and_parses_json(captured_provider):
    captured_provider["next"] = _response(
        json.dumps(
            {
                "summary_a": "edits",
                "summary_b": "color",
                "conflicts": [],
                "recommendation": "accept_a",
                "explanation": "ours has more",
            }
        )
    )
    result = analyze_branch_comparison(
        "main",
        "feature",
        {"video": [{"id": "x", "type": "trim"}]},
        {"color": [{"id": "x", "type": "grade"}]},
    )
    assert result["recommendation"] == "accept_a"
    assert result["explanation"].startswith("ours")


# ---------- heuristic fallback contract ----------


def test_ai_analyze_merge_heuristic_provider_returns_empty_analysis(force_heuristic):
    """HeuristicProvider returns an empty-decisions envelope; ai_analyze_merge
    must parse it as a valid (if useless) MergeAnalysis and NOT crash."""
    result = ai_analyze_merge({}, {}, {}, [], [])
    assert isinstance(result, MergeAnalysis)
    assert result.decisions == []
    assert not result.needs_user_input()


def test_classify_commit_falls_back_to_core_heuristic_when_ai_refuses(monkeypatch):
    """If the provider returns ok=False, classify_commit must still produce
    one of ("audio","video","color") via categorize_commit."""

    class _Refusing:
        name = "refuse"

        def is_available(self):
            return True

        def complete(self, system, user, *, json_mode=False):
            return AIResponse(text="", ok=False, provider="refuse")

    monkeypatch.setattr("vit.ai_merge.get_provider", lambda *a, **k: _Refusing())

    # Mixed files that won't trigger the 60% heuristic shortcut.
    result = classify_commit_type(
        "abc", ["timeline/metadata.json", "timeline/markers.json"]
    )
    assert result in ("audio", "video", "color")
