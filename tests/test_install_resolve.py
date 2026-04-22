"""Tests for `vit install-resolve` — the command that copies/symlinks
the panel script into DaVinci Resolve's scripts tree.

The real command writes to %APPDATA% (Windows) or ~/Library (macOS);
here we redirect both the scripts root and the package-path file to a
tmp dir via monkeypatch so the test is hermetic.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

from vit import cli


def _fake_plugin_tree(root: str) -> str:
    """Create a minimal 'vit source' layout in `root` so install-resolve
    has something to read from. Returns the package_dir path the command
    will see via dirname(dirname(cli.__file__))."""
    os.makedirs(os.path.join(root, "vit"), exist_ok=True)
    with open(os.path.join(root, "vit", "__init__.py"), "w") as f:
        f.write("")
    # Create cli.py so find_package_root derives the right paths
    with open(os.path.join(root, "vit", "cli.py"), "w") as f:
        f.write("")
    os.makedirs(os.path.join(root, "resolve_plugin"), exist_ok=True)
    with open(os.path.join(root, "resolve_plugin", "__init__.py"), "w") as f:
        f.write("")
    with open(os.path.join(root, "resolve_plugin", "vit_panel.py"), "w") as f:
        f.write("# fake panel script\n")
    return root


@pytest.fixture
def isolated_install(tmp_path, monkeypatch):
    """Redirect install-resolve's target dir + user dir to tmp_path."""
    scripts_root = tmp_path / "resolve" / "Fusion" / "Scripts"
    scripts_root.mkdir(parents=True)
    user_home = tmp_path / "home"
    user_home.mkdir()

    # RESOLVE_SCRIPTS_DIR is computed once at import. Override the
    # module-level attribute for the test.
    monkeypatch.setattr(cli, "RESOLVE_SCRIPTS_DIR", str(scripts_root / "Edit"))
    # Expanduser("~") -> our tmp home so package_path + anything else
    # lands inside the sandbox.
    if sys.platform == "win32":
        monkeypatch.setenv("USERPROFILE", str(user_home))
    monkeypatch.setenv("HOME", str(user_home))

    yield SimpleNamespace(
        scripts_root=scripts_root,
        edit_dir=scripts_root / "Edit",
        utility_dir=scripts_root / "Utility",
        user_home=user_home,
    )


def _stub_package_dir(tmp_path, monkeypatch):
    """Make os.path.dirname(dirname(cli.__file__)) resolve to a fake tree."""
    fake_pkg = tmp_path / "fake_pkg"
    _fake_plugin_tree(str(fake_pkg))
    # Replace cli.__file__ so cmd_install_resolve's dirname math lands here.
    monkeypatch.setattr(cli, "__file__", str(fake_pkg / "vit" / "cli.py"))
    return fake_pkg


def test_install_resolve_copies_into_utility_and_edit(
    isolated_install, tmp_path, monkeypatch
):
    _stub_package_dir(tmp_path, monkeypatch)

    # Command calls sys.exit only on failure; we don't expect it to exit here.
    cli.cmd_install_resolve(SimpleNamespace())

    assert (isolated_install.utility_dir / "Vit.py").exists()
    assert (isolated_install.edit_dir / "Vit.py").exists()


def test_install_resolve_writes_package_path(isolated_install, tmp_path, monkeypatch):
    fake_pkg = _stub_package_dir(tmp_path, monkeypatch)

    cli.cmd_install_resolve(SimpleNamespace())

    pkg_path_file = isolated_install.user_home / ".vit" / "package_path"
    assert pkg_path_file.exists()
    recorded = pkg_path_file.read_text().strip()
    assert recorded == str(fake_pkg)


def test_install_resolve_is_idempotent(isolated_install, tmp_path, monkeypatch):
    """Running install twice must leave exactly one copy in each target
    dir, not crash on the pre-existing file, not duplicate."""
    _stub_package_dir(tmp_path, monkeypatch)
    cli.cmd_install_resolve(SimpleNamespace())
    # Mtime check: second run should replace (not duplicate) the file.
    first_mtime = (isolated_install.utility_dir / "Vit.py").stat().st_mtime

    import time

    time.sleep(0.05)  # ensure a detectable mtime delta

    cli.cmd_install_resolve(SimpleNamespace())

    # Only one Vit.py per target dir.
    assert list(isolated_install.utility_dir.glob("Vit*.py")) == [
        isolated_install.utility_dir / "Vit.py"
    ]
    assert list(isolated_install.edit_dir.glob("Vit*.py")) == [
        isolated_install.edit_dir / "Vit.py"
    ]
    # And the second install actually rewrote the file.
    second_mtime = (isolated_install.utility_dir / "Vit.py").stat().st_mtime
    assert second_mtime >= first_mtime


def test_install_resolve_fails_when_plugin_dir_missing(
    isolated_install, tmp_path, monkeypatch
):
    """If vit was installed as a wheel that somehow omits resolve_plugin,
    cmd_install_resolve must sys.exit(1) with a clear error."""
    broken_pkg = tmp_path / "broken"
    os.makedirs(os.path.join(broken_pkg, "vit"), exist_ok=True)
    # no resolve_plugin/ dir at all
    monkeypatch.setattr(cli, "__file__", str(broken_pkg / "vit" / "cli.py"))
    # Also kill the ~/.vit/vit-src fallback.
    monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
    if sys.platform == "win32":
        monkeypatch.setenv("USERPROFILE", str(tmp_path / "empty_home"))

    with pytest.raises(SystemExit) as exc:
        cli.cmd_install_resolve(SimpleNamespace())
    assert exc.value.code == 1


def test_uninstall_resolve_removes_from_all_known_subdirs(
    isolated_install, tmp_path, monkeypatch
):
    _stub_package_dir(tmp_path, monkeypatch)
    cli.cmd_install_resolve(SimpleNamespace())

    # Sanity: files exist before uninstall
    assert (isolated_install.utility_dir / "Vit.py").exists()
    assert (isolated_install.edit_dir / "Vit.py").exists()

    cli.cmd_uninstall_resolve(SimpleNamespace())

    assert not (isolated_install.utility_dir / "Vit.py").exists()
    assert not (isolated_install.edit_dir / "Vit.py").exists()


def test_uninstall_resolve_is_harmless_when_nothing_installed(
    isolated_install, tmp_path, monkeypatch, capsys
):
    _stub_package_dir(tmp_path, monkeypatch)
    cli.cmd_uninstall_resolve(SimpleNamespace())
    out = capsys.readouterr().out
    assert "No vit scripts found" in out
