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

    EXPIRED_CREDENTIALS is special: the connection loop's own thread keeps
    running and polling in this state (_wait_for_valid_tokens() in
    connection_runner.py) and transitions itself back into the loop once
    tokens are valid again, with no external call needed. Anything that
    wants to *replace* a record sitting in EXPIRED_CREDENTIALS (e.g. a
    manual reconnect from the UI) must call ForwarderRegistry.stop_one()
    on it first — its background thread may still be alive and holding
    resources (ssm_proc, pf) that a fresh record won't know about.

Terminal states (no further transitions out on their own):
    STOPPED, ERROR, EXPIRED_CREDENTIALS. Note EXPIRED_CREDENTIALS can still
    self-resume from inside its own thread; it is "terminal" only in that
    nothing outside that thread can move it forward.

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
