"""Runtime hook to ensure charset_normalizer is importable before requests loads."""

import charset_normalizer  # noqa: F401 - force import so requests finds it
