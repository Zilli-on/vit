"""Interactive merge dialog — pure-Python core + optional Qt UI.

The upstream CLI flow drops the user into raw stdin `input()` prompts
for each `needs_user_input` merge decision. That's unusable for
non-technical editors, so this module offers two interchangeable
frontends:

  * `CliMergeDialog`  — compatible with the upstream behavior, prints
                        decisions, reads choices from stdin.
  * `QtMergeDialog`   — PySide6 modal with one card per decision,
                        radio buttons for options, Apply / Cancel.

Both return the same dict of {domain: option_key} so the downstream
`ai_resolve_clarifications` call is identical.

The core (`MergeDialog` base) is testable without Qt.
"""

from __future__ import annotations

import sys
from typing import Dict, List, Optional, Protocol

from .ai_merge import MergeAnalysis, MergeDecision


class MergeDialog(Protocol):
    def show(self, analysis: MergeAnalysis) -> Optional[Dict[str, str]]:
        """Render decisions, collect user's answers.

        Returns dict of {domain: option_key}, or None if user cancels.
        """
        ...


def format_auto_resolved(decisions: List[MergeDecision]) -> List[str]:
    """Pretty lines for decisions the AI resolved without user input."""
    out = []
    for d in decisions:
        icon = {"high": "+", "medium": "~", "low": "?"}.get(d.confidence, "?")
        out.append(f"[{icon}] {d.domain}: {d.action}  ({d.confidence})")
        if d.reasoning:
            out.append(f"     {d.reasoning}")
    return out


def format_question(d: MergeDecision) -> List[str]:
    """Pretty lines for one open decision."""
    out = [f"[?] {d.domain}  —  {d.reasoning}"]
    for opt in d.options:
        label = f"     {opt.key}) {opt.label}"
        if opt.description:
            label += f"  —  {opt.description}"
        out.append(label)
    return out


class CliMergeDialog:
    """Same behavior as the upstream interactive stdin flow, but split
    out as a class so it can be swapped or tested."""

    name = "cli"

    def __init__(self, stdin=None, stdout=None):
        self._in = stdin or sys.stdin
        self._out = stdout or sys.stdout

    def _write(self, line: str = "") -> None:
        self._out.write(line + "\n")

    def show(self, analysis: MergeAnalysis) -> Optional[Dict[str, str]]:
        auto = analysis.get_auto_resolved()
        questions = analysis.get_questions()

        self._write("")
        self._write(f"  AI merge analysis: {analysis.summary}")
        self._write("  " + "=" * 50)
        if auto:
            self._write("  Auto-resolved:")
            for line in format_auto_resolved(auto):
                self._write(f"    {line}")
            self._write("")
        if not questions:
            return {}

        self._write("  Decisions requiring your input:")
        for d in questions:
            for line in format_question(d):
                self._write(f"    {line}")
        self._write("")

        answers: Dict[str, str] = {}
        for d in questions:
            valid = [o.key.upper() for o in d.options]
            while True:
                prompt = f"    {d.domain} [{'/'.join(valid)}]: "
                try:
                    self._out.write(prompt)
                    self._out.flush()
                    raw = self._in.readline()
                except (EOFError, KeyboardInterrupt):
                    self._write("\n  Merge cancelled.")
                    return None
                if not raw:
                    self._write("\n  Merge cancelled.")
                    return None
                choice = raw.strip().upper()
                if choice in valid:
                    answers[d.domain] = choice
                    break
                self._write(f"      Invalid. Use one of: {'/'.join(valid)}")
        return answers


class QtMergeDialog:
    """PySide6 modal. Imports Qt lazily so missing PySide6 doesn't break
    the module import and leaves the CLI flow intact."""

    name = "qt"

    def show(self, analysis: MergeAnalysis) -> Optional[Dict[str, str]]:
        try:
            from PySide6.QtWidgets import (
                QApplication,
                QDialog,
                QVBoxLayout,
                QHBoxLayout,
                QLabel,
                QRadioButton,
                QButtonGroup,
                QPushButton,
                QFrame,
                QScrollArea,
                QWidget,
            )
            from PySide6.QtCore import Qt
        except Exception:
            return CliMergeDialog().show(analysis)

        app = QApplication.instance() or QApplication(sys.argv)

        dlg = QDialog()
        dlg.setWindowTitle("Vit — resolve merge")
        dlg.setMinimumWidth(520)
        dlg.setMinimumHeight(420)
        root = QVBoxLayout(dlg)

        summary = QLabel(f"<b>Summary:</b> {analysis.summary or '(none)'}")
        summary.setWordWrap(True)
        root.addWidget(summary)

        auto = analysis.get_auto_resolved()
        if auto:
            auto_box = QLabel(
                "<b>Auto-resolved:</b><br>" + "<br>".join(format_auto_resolved(auto))
            )
            auto_box.setTextFormat(Qt.RichText)
            auto_box.setWordWrap(True)
            root.addWidget(auto_box)

        questions = analysis.get_questions()
        groups: Dict[str, QButtonGroup] = {}

        if questions:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            inner = QWidget()
            inner_layout = QVBoxLayout(inner)

            for d in questions:
                card = QFrame()
                card.setFrameShape(QFrame.StyledPanel)
                v = QVBoxLayout(card)
                title = QLabel(f"<b>{d.domain}</b>  —  {d.reasoning}")
                title.setWordWrap(True)
                v.addWidget(title)
                group = QButtonGroup(card)
                for i, opt in enumerate(d.options):
                    text = opt.label
                    if opt.description:
                        text += f" — {opt.description}"
                    rb = QRadioButton(f"{opt.key})  {text}")
                    if i == 0:
                        rb.setChecked(True)
                    group.addButton(rb, i)
                    v.addWidget(rb)
                groups[d.domain] = group
                inner_layout.addWidget(card)

            inner_layout.addStretch(1)
            scroll.setWidget(inner)
            root.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btn_cancel = QPushButton("Cancel")
        btn_apply = QPushButton("Apply")
        btn_apply.setDefault(True)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_apply)
        root.addLayout(buttons)

        btn_cancel.clicked.connect(dlg.reject)
        btn_apply.clicked.connect(dlg.accept)

        result = dlg.exec()
        if result != QDialog.Accepted:
            return None

        answers: Dict[str, str] = {}
        for d in questions:
            group = groups[d.domain]
            idx = group.checkedId()
            if 0 <= idx < len(d.options):
                answers[d.domain] = d.options[idx].key.upper()
        return answers


def pick_dialog(preferred: Optional[str] = None) -> MergeDialog:
    """Pick the best dialog for the environment.

    Order:
      - explicit `preferred` ("qt" / "cli")
      - VIT_MERGE_UI env var
      - qt if PySide6 importable AND a display is likely available
      - cli otherwise
    """
    import os

    choice = (preferred or os.environ.get("VIT_MERGE_UI") or "").strip().lower()
    if choice == "cli":
        return CliMergeDialog()
    if choice == "qt":
        return QtMergeDialog()

    # Auto-pick
    try:
        import PySide6  # noqa: F401

        return QtMergeDialog()
    except ImportError:
        return CliMergeDialog()
