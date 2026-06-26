"""Connection state machine for SSM database tunnels.

A `ConnectionRecord.state` transitions through these values during its
lifetime. Centralizing them here keeps the state machine explicit, prevents
typos, and lets both the runner and its tests refer to one source of truth.

Lifecycle:
    STARTING -> CONNECTING -> CONNECTED
                              |
                              v
                          RECONNECTING (on drop, when tokens are valid)
                              |
                              v
                          CONNECTED (next attempt) or one of the terminal
                          states below.

Terminal states (no further transitions out):
    STOPPED, ERROR, EXPIRED_CREDENTIALS.

Transient states (not yet considered stable by the probe-guard):
    STARTING, CONNECTING.
"""

# Connection lifecycle states
STARTING = "starting"
CONNECTING = "connecting"
CONNECTED = "connected"
RECONNECTING = "reconnecting"
EXPIRED_CREDENTIALS = "expired_credentials"
ERROR = "error"
STOPPED = "stopped"

# Sets for state-guard checks
TRANSIENT_STATES: frozenset[str] = frozenset({STARTING, CONNECTING})
TERMINAL_STATES: frozenset[str] = frozenset({STOPPED, ERROR, EXPIRED_CREDENTIALS})

# Probe timeout (seconds) — moved from hardcoded 15.0 in connection_runner.py
PROBE_TIMEOUT_SECONDS: float = 60.0
