"""Structural guard: package.json scripts must never self-recursively invoke npm.

Bug class (3rd occurrence in this workspace, 2026-08-25): template-junk npm
scripts on a Python project. ``"test": "npm test -- ..."`` re-invokes itself
until ELOOP/core dump; ``prepare -> build -> npm run test`` crashed every
``npm install``. Precedent: agent-memory-kit scripts={} DOA (655c173),
ai-dev-tools vanity tests (e542697). This file makes the wiring regression
visible to pytest.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = json.load(open(os.path.join(HERE, "package.json"), encoding="utf-8"))
SCRIPTS = PKG.get("scripts", {})

# Scripts that must exist and point at the real (pytest) runner.
REQUIRED = ("test", "test:verbose", "test:coverage", "build", "dev", "lint")


def test_required_scripts_exist():
    missing = [k for k in REQUIRED if k not in SCRIPTS]
    assert not missing, f"missing npm scripts: {missing}"


def test_no_script_self_recurses():
    for name, cmd in SCRIPTS.items():
        assert "npm test" not in cmd, f"script {name!r} re-invokes npm test: {cmd!r}"
        assert "npm run" not in cmd, f"script {name!r} chains via npm run: {cmd!r}"


def test_test_script_invokes_pytest():
    assert "pytest" in SCRIPTS["test"], SCRIPTS["test"]
    assert "python3" in SCRIPTS["test"], SCRIPTS["test"]


def test_no_publish_lifecycle_hooks():
    # prepare/prepublishOnly/version re-trigger build chains on npm install;
    # this is a Python package, not an npm artifact.
    for hook in ("prepare", "prepublishOnly", "version"):
        assert hook not in SCRIPTS, f"npm lifecycle hook {hook!r} present: {SCRIPTS[hook]!r}"


def test_lint_targets_existing_files():
    targets = [t for t in SCRIPTS["lint"].split() if t.endswith(".py")]
    assert targets, "lint script has no .py targets"
    missing = [t for t in targets if not os.path.exists(os.path.join(HERE, t))]
    assert not missing, f"lint targets missing files: {missing}"


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-q", __file__]))
