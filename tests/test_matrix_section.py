"""Smoke + render tests for the Qt MatrixSection widget.

These tests use the QApplication 'offscreen' platform so they don't
need a display server. Skipped if PySide6 isn't importable (Tkinter
fallback users).
"""

from __future__ import annotations

import json
import os
import sys

import pytest


PYSIDE6 = pytest.importorskip("PySide6.QtWidgets")
# Must be set before QApplication is created.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def section(qt_app):
    from resolve_plugin.vit_panel_qt import MatrixSection

    return MatrixSection()


@pytest.fixture
def project_with_variants(tmp_path):
    """Full vit project with 2 registered variants."""
    from vit.core import git_init
    from vit.matrix import cmd_add

    p = str(tmp_path / "proj")
    git_init(p)
    import subprocess

    subprocess.run(["git", "config", "user.email", "t@t"], cwd=p, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=p, check=True)
    subprocess.run(["git", "add", "-A"], cwd=p, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=p, check=True)

    cmd_add(p, "9x16", format_label="9x16-30s")
    cmd_add(p, "1x1", format_label="1x1-60s")
    return p


def _collect_labels(section) -> list[str]:
    """Flatten every QLabel text under the body layout."""
    from PySide6.QtWidgets import QLabel

    texts = []

    def walk(layout):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            w = item.widget()
            if isinstance(w, QLabel):
                texts.append(w.text())
            elif w is not None and w.layout() is not None:
                walk(w.layout())
            else:
                nested = item.layout()
                if nested is not None:
                    walk(nested)

    walk(section._body_layout)
    return texts


def test_empty_state_before_set_project_dir(section):
    labels = _collect_labels(section)
    assert any("No project loaded" in t for t in labels)


def test_renders_empty_state_when_no_variants_file(section, tmp_path):
    from vit.core import git_init

    p = str(tmp_path / "empty-proj")
    git_init(p)
    section.set_project_dir(p)

    labels = _collect_labels(section)
    joined = " ".join(labels)
    assert "No variants registered" in joined


def test_renders_row_per_variant(section, project_with_variants):
    section.set_project_dir(project_with_variants)
    labels = _collect_labels(section)

    # Variant names + format labels visible
    assert any("9x16" == t or "9x16" in t for t in labels)
    assert any("9x16-30s" == t for t in labels)
    assert any("1x1" == t or "1x1" in t for t in labels)
    assert any("1x1-60s" == t for t in labels)
    # Header row present
    assert "VARIANT" in labels
    assert "FORMAT" in labels
    assert "BEHIND" in labels
    assert "REDERIVE" in labels


def test_behind_zero_right_after_add(section, project_with_variants):
    section.set_project_dir(project_with_variants)
    labels = _collect_labels(section)
    # Expect two "0" labels (one per variant; matrix._commits_behind on a
    # freshly-added variant returns 0 because parent is at the same
    # commit).
    zero_count = sum(1 for t in labels if t == "0")
    assert zero_count >= 2


def test_refresh_reflects_disk_changes(section, project_with_variants):
    """Mutating variants.json from outside then calling refresh should
    update the rendered state (no stale cache)."""
    section.set_project_dir(project_with_variants)
    before = _collect_labels(section)
    assert any("9x16" in t for t in before)

    # Remove one variant on disk.
    path = os.path.join(project_with_variants, ".vit", "variants.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["variants"].pop("9x16")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)

    section.refresh()
    after = _collect_labels(section)
    # 9x16 should be gone; 1x1 still there.
    assert all("9x16" not in t for t in after)
    assert any("1x1" in t for t in after)


def test_humanize_variants(section):
    """Pure-function unit tests for the timestamp humanizer."""
    import time

    from resolve_plugin.vit_panel_qt import MatrixSection

    assert MatrixSection._humanize(0) == "never"
    assert MatrixSection._humanize(-1) == "never"
    assert MatrixSection._humanize("garbage") == "never"
    # "just now" threshold is < 60s.
    assert MatrixSection._humanize(time.time()) == "just now"
