"""Tests for plugins/version_control.py — VersionControl stub.

Restores the real module in sys.modules and saves/restores the mock
to avoid breaking other tests' expectations.
"""

import importlib
import sys
from pathlib import Path

import pytest


def _get_real_class():
    """Get the real VersionControl class, restoring mock afterward."""
    saved = sys.modules.get("plugins.version_control")
    # Load real module
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "plugins.version_control",
        "/root/.openclaw/workspace/better-ralph-core/plugins/version_control.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.VersionControl


class TestVersionControl:
    def test_default_init(self):
        VC = _get_real_class()
        vc = VC()
        assert vc.project_root is None

    def test_init_with_path(self):
        VC = _get_real_class()
        p = Path("/tmp/test")
        vc = VC(project_root=p)
        assert vc.project_root == p

    def test_commit_returns_none(self):
        VC = _get_real_class()
        vc = VC()
        assert vc.commit("msg") is None

    def test_commit_with_files_returns_none(self):
        VC = _get_real_class()
        vc = VC()
        assert vc.commit("msg", files=["a.py", "b.py"]) is None

    def test_get_status_empty(self):
        VC = _get_real_class()
        vc = VC()
        assert vc.get_status() == {}

    def test_get_status_returns_dict(self):
        VC = _get_real_class()
        vc = VC(project_root=Path("."))
        result = vc.get_status()
        assert isinstance(result, dict)
