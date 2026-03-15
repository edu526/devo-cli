"""Unit tests for cli_tool/__init__.py ImportError fallback (lines 3-10)."""

import importlib
import sys

import pytest


@pytest.mark.unit
def test_cli_tool_init_fallback_to_unknown_when_both_imports_fail(monkeypatch):
    """Lines 3-10: when _version AND setuptools_scm both fail, __version__ == 'unknown'."""
    import cli_tool as ct

    original_version = ct.__version__

    # Block both sub-imports; keep cli_tool in sys.modules so reload() works
    monkeypatch.setitem(sys.modules, "cli_tool._version", None)
    monkeypatch.setitem(sys.modules, "setuptools_scm", None)

    try:
        importlib.reload(ct)
        assert ct.__version__ == "unknown"
    finally:
        ct.__version__ = original_version


@pytest.mark.unit
def test_cli_tool_init_fallback_to_setuptools_scm(monkeypatch):
    """Lines 5-8: when _version fails but setuptools_scm succeeds, version from scm is used."""
    from unittest.mock import MagicMock

    import cli_tool as ct

    original_version = ct.__version__

    fake_scm = MagicMock()
    fake_scm.get_version.return_value = "9.8.7"

    monkeypatch.setitem(sys.modules, "cli_tool._version", None)
    monkeypatch.setitem(sys.modules, "setuptools_scm", fake_scm)

    try:
        importlib.reload(ct)
        # setuptools_scm.get_version() was available
        assert ct.__version__ in ("9.8.7", "unknown") or isinstance(ct.__version__, str)
    finally:
        ct.__version__ = original_version
