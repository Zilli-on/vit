"""Unit tests for vit.doctor.

Probes are stubbed where possible. We don't care whether Ollama is
running in CI; we only care that the probe returns a Check with valid
status and doesn't raise.
"""

from __future__ import annotations

import os
from unittest.mock import patch


from vit.doctor import (
    Check,
    _ICON,
    _probe_claude_cli,
    _probe_gemini_key,
    _probe_git,
    _probe_ollama,
    _probe_python,
    _probe_resolve_install,
    any_fails,
    format_report,
    run_diagnostics,
)


def test_probe_python_reports_ok_on_modern_python():
    c = _probe_python()
    assert isinstance(c, Check)
    assert c.status == "OK"
    assert "3." in c.detail


def test_probe_git_detects_binary():
    # git must be present in the dev env, otherwise the tests wouldn't run
    c = _probe_git()
    assert c.status in ("OK", "WARN")
    if c.status == "OK":
        assert "git version" in c.detail


def test_probe_resolve_install_returns_ok_or_warn():
    c = _probe_resolve_install()
    assert c.status in ("OK", "WARN")
    if c.status == "WARN":
        assert c.fix  # WARN must include a fix suggestion


def test_probe_gemini_key_masks_key():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "abcd1234xyz9"}, clear=False):
        c = _probe_gemini_key()
        assert c.status == "OK"
        assert "abcd" in c.detail
        assert "xyz9" in c.detail
        # Middle of the key must not leak
        assert "1234xy" not in c.detail


def test_probe_gemini_key_warns_when_missing():
    env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        c = _probe_gemini_key()
        assert c.status == "WARN"
        assert c.fix


def test_probe_ollama_returns_valid_status():
    c = _probe_ollama()
    assert c.status in ("OK", "WARN")


def test_probe_claude_cli_handles_absence():
    with patch("shutil.which", return_value=None):
        c = _probe_claude_cli()
        assert c.status == "WARN"


def test_probe_claude_cli_handles_presence():
    with patch("shutil.which", return_value="/fake/path/claude"):
        c = _probe_claude_cli()
        assert c.status == "OK"
        assert "/fake/path/claude" in c.detail


def test_run_diagnostics_returns_all_probes():
    checks = run_diagnostics()
    # Sanity: at minimum the core probes fire
    names = {c.name for c in checks}
    assert "Python version" in names
    assert "git" in names
    # No probe may raise past the caller
    for c in checks:
        assert isinstance(c, Check)
        assert c.status in ("OK", "WARN", "FAIL")


def test_format_report_renders_all_icons():
    checks = [
        Check("one", "OK", "detail one"),
        Check("two", "WARN", "detail two", fix="fix two"),
        Check("three", "FAIL", "detail three", fix="fix three"),
    ]
    report = format_report(checks)
    for icon in _ICON.values():
        assert icon in report
    assert "summary: 1 ok, 1 warn, 1 fail" in report
    assert "-> fix two" in report
    assert "-> fix three" in report


def test_any_fails_detects_fails():
    assert any_fails([Check("x", "FAIL", "bad")]) is True
    assert any_fails([Check("x", "WARN", "meh")]) is False
    assert any_fails([Check("x", "OK", "good")]) is False


def test_run_diagnostics_never_crashes(monkeypatch):
    """A broken probe must fail gracefully, not take down the run."""
    import vit.doctor as d

    def boom():
        raise RuntimeError("simulated probe failure")

    monkeypatch.setattr(d, "_PROBES", [boom])
    checks = d.run_diagnostics()
    assert len(checks) == 1
    assert checks[0].status == "FAIL"
    assert "probe crashed" in checks[0].detail
