"""Whether Devo maps a database's hostname to its tunnel in the hosts file.

Hostname forwarding points the database's real hostname at the tunnel's
loopback IP, so clients connect to the same name as without Devo. Turning it
off lets the name resolve through normal DNS again, so it can be reached some
other way (a VPN, the office network…), while a tunnel can still be opened on
127.0.0.1.

`ssm.hostname_forwarding` is the setting for every database (on by default,
also for databases added later); `ssm.databases.<name>.hostname_forwarding`,
when present, is an exception for that one. So with everything paused, one
database can still be forwarded, and the other way around.
"""

from typing import Any

KEY = "hostname_forwarding"


def global_enabled(ssm_config: dict[str, Any]) -> bool:
    return ssm_config.get(KEY, True) is not False


def is_enabled(ssm_config: dict[str, Any], db_config: dict[str, Any]) -> bool:
    own = db_config.get(KEY)
    return global_enabled(ssm_config) if own is None else own is not False
