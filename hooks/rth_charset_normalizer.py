"""Runtime hook to ensure a charset detection library is importable before requests loads.

chardet is pure Python and bundles reliably across all platforms. charset_normalizer
is also included but may lack its compiled C extension (md__mypyc) on some CI environments.
Having chardet as a fallback prevents the RequestsDependencyWarning from requests.
"""

import chardet  # noqa: F401 - ensures requests finds a charset detection library
import charset_normalizer  # noqa: F401
