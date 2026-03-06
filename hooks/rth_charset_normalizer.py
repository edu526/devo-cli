"""Runtime hook: ensure a charset detection library is importable before requests loads.

chardet is pure Python and always bundles reliably. charset_normalizer binary wheels
on some platforms (e.g. macOS universal2) contain mypyc-compiled modules with
hash-based names that PyInstaller cannot resolve — so we import it defensively.
"""

try:
    import charset_normalizer  # noqa: F401
except Exception:
    pass

import chardet  # noqa: F401 - guaranteed pure-Python fallback for requests
