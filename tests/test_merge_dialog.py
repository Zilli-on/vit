"""Unit tests for vit.merge_dialog — CLI dialog + picker.

Qt dialog isn't unit-tested (needs a display + Qt event loop); it's
exercised manually against Resolve.
"""

from __future__ import annotations

import io
from unittest.mock import patch


from vit.ai_merge import MergeAnalysis, MergeDecision, MergeOption
from vit.merge_dialog import (
    CliMergeDialog,
    QtMergeDialog,
    format_auto_resolved,
    format_question,
    pick_dialog,
)


def _analysis_with_one_question():
    return MergeAnalysis(
        summary="Both changed saturation",
        decisions=[
            MergeDecision(
                domain="cuts",
                action="accept_theirs",
                confidence="high",
                reasoning="Only theirs changed cuts",
            ),
            MergeDecision(
                domain="color",
                action="needs_user_input",
                confidence="low",
                reasoning="Both branches changed saturation",
                options=[
                    MergeOption(key="A", label="Keep ours", description="warmer"),
                    MergeOption(key="B", label="Keep theirs", description="cooler"),
                ],
            ),
        ],
    )


def test_format_auto_resolved_emits_confidence_icon():
    analysis = _analysis_with_one_question()
    lines = format_auto_resolved(analysis.get_auto_resolved())
    assert any("[+]" in line for line in lines)
    assert any("cuts" in line for line in lines)


def test_format_question_lists_all_options():
    analysis = _analysis_with_one_question()
    lines = format_question(analysis.get_questions()[0])
    assert any("color" in line for line in lines)
    assert any("Keep ours" in line for line in lines)
    assert any("Keep theirs" in line for line in lines)


def test_cli_dialog_accepts_first_option():
    analysis = _analysis_with_one_question()
    stdin = io.StringIO("A\n")
    stdout = io.StringIO()
    answers = CliMergeDialog(stdin=stdin, stdout=stdout).show(analysis)
    assert answers == {"color": "A"}


def test_cli_dialog_rejects_invalid_then_accepts():
    analysis = _analysis_with_one_question()
    stdin = io.StringIO("Z\nB\n")
    stdout = io.StringIO()
    answers = CliMergeDialog(stdin=stdin, stdout=stdout).show(analysis)
    assert answers == {"color": "B"}
    assert "Invalid" in stdout.getvalue()


def test_cli_dialog_returns_none_on_eof():
    analysis = _analysis_with_one_question()
    stdin = io.StringIO("")  # immediate EOF
    stdout = io.StringIO()
    answers = CliMergeDialog(stdin=stdin, stdout=stdout).show(analysis)
    assert answers is None


def test_cli_dialog_empty_when_no_questions():
    analysis = MergeAnalysis(
        summary="Nothing to ask",
        decisions=[
            MergeDecision(
                domain="cuts",
                action="accept_ours",
                confidence="high",
                reasoning="",
            )
        ],
    )
    stdin = io.StringIO("")  # should never be read
    answers = CliMergeDialog(stdin=stdin, stdout=io.StringIO()).show(analysis)
    assert answers == {}


def test_pick_dialog_honors_explicit_cli():
    d = pick_dialog(preferred="cli")
    assert isinstance(d, CliMergeDialog)


def test_pick_dialog_honors_env_cli(monkeypatch):
    monkeypatch.setenv("VIT_MERGE_UI", "cli")
    d = pick_dialog()
    assert isinstance(d, CliMergeDialog)


def test_pick_dialog_falls_back_to_cli_when_no_qt(monkeypatch):
    monkeypatch.delenv("VIT_MERGE_UI", raising=False)

    # Simulate PySide6 import failure
    import builtins

    real_import = builtins.__import__

    def fail_import(name, *args, **kwargs):
        if name == "PySide6":
            raise ImportError("no PySide6")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fail_import):
        d = pick_dialog()
    assert isinstance(d, CliMergeDialog)


def test_qt_dialog_falls_back_when_pyside6_missing(monkeypatch):
    """If Qt import fails inside show(), QtMergeDialog must delegate to
    CliMergeDialog instead of raising."""
    import builtins

    real_import = builtins.__import__

    def fail_import(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("no PySide6")
        return real_import(name, *args, **kwargs)

    analysis = MergeAnalysis(summary="x", decisions=[])
    with patch("builtins.__import__", side_effect=fail_import):
        result = QtMergeDialog().show(analysis)
    # No questions → CLI dialog returns empty dict, not None
    assert result == {}
