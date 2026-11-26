"""Import tests for a core-only install (no optional extras).

A plain ``pip install cachibot`` ships only the core dependencies — no
sqlalchemy, no aiohttp. Importing the package, the plugin registry, and the
Typer CLI app must still work there: the computer/coding-agent/file-ops/Faro
plugins load their services lazily, on first use.

These tests run a subprocess with a meta-path blocker that makes
sqlalchemy/aiohttp raise ModuleNotFoundError, simulating the slim install
without uninstalling anything from the test environment.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Makes ``import sqlalchemy`` / ``import aiohttp`` (and their submodules) fail
# the same way a core-only install does, for everything imported after it is
# installed.
_BLOCK_EXTRAS = """\
import sys


class _MissingExtras:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("sqlalchemy", "aiohttp"):
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return None


sys.meta_path.insert(0, _MissingExtras())
"""


def _run_with_blocked_extras(script: str, home: Path) -> "subprocess.CompletedProcess[str]":
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "CACHIBOT_TELEMETRY_DISABLED": "1",
        "HOME": str(home),
    }
    return subprocess.run(
        [sys.executable, "-c", _BLOCK_EXTRAS + script],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def test_import_cachibot_without_optional_extras(tmp_path: Path) -> None:
    """import cachibot / cachibot.plugins / cachibot.cli need no extras."""
    script = """\
import sys

import cachibot
import cachibot.plugins
from cachibot.cli import app

assert "sqlalchemy" not in sys.modules, "sqlalchemy imported on a core-only install"
assert "aiohttp" not in sys.modules, "aiohttp imported on a core-only install"
assert app is not None
"""
    result = _run_with_blocked_extras(script, tmp_path)
    assert result.returncode == 0, result.stderr


def _analysis_keyword_strings(spec_path: Path, keyword: str) -> set[str]:
    """String constants listed under an ``Analysis(...)`` keyword in a spec."""
    tree = ast.parse(spec_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Analysis"):
            continue
        for kw in node.keywords:
            if kw.arg == keyword:
                return {
                    elt.value
                    for elt in ast.walk(kw.value)
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                }
    raise AssertionError(f"{keyword!r} not found in {spec_path.name}")


def test_pyinstaller_specs_bundle_aiohttp_only_for_server() -> None:
    """Faro is a server feature: the mini server must bundle aiohttp, while
    the slim CLI keeps excluding it."""
    mini_spec = REPO_ROOT / "cachibot-server-mini.spec"
    assert "aiohttp" not in _analysis_keyword_strings(mini_spec, "excludes")
    assert "aiohttp" in _analysis_keyword_strings(mini_spec, "hiddenimports")
    cli_excludes = _analysis_keyword_strings(REPO_ROOT / "cachibot-cli.spec", "excludes")
    assert "aiohttp" in cli_excludes


def test_cli_help_without_optional_extras(tmp_path: Path) -> None:
    """The Typer app help path (``cachi --help``) needs no sqlalchemy/aiohttp."""
    script = """\
import sys

from typer.testing import CliRunner

from cachibot.cli import app

result = CliRunner().invoke(app, ["--help"])
assert result.exit_code == 0, result.output
assert "sqlalchemy" not in sys.modules, "sqlalchemy imported by cachi --help"
assert "aiohttp" not in sys.modules, "aiohttp imported by cachi --help"
"""
    result = _run_with_blocked_extras(script, tmp_path)
    assert result.returncode == 0, result.stderr
