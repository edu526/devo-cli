"""Runtime hook: ensure charset_normalizer is importable before requests loads.

charset_normalizer is the standard charset detection library used by requests.
This hook ensures it's available in the PyInstaller bundle.

Note: chardet is no longer needed as requests uses charset_normalizer by default
since v2.26.0 (2021), and PyInstaller 5.0+ handles it correctly.
"""

try:
    import charset_normalizer  # noqa: F401
except Exception:
    # If charset_normalizer fails, requests will use its built-in fallback
    pass
