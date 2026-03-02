"""AWS Systems Manager Session Manager integration"""

# Backward compatibility imports
from cli_tool.ssm.core import PortForwarder, SSMConfigManager, SSMSession
from cli_tool.ssm.utils import HostsManager

# Backward compatibility alias
SocatManager = PortForwarder

__all__ = ["SSMConfigManager", "SSMSession", "HostsManager", "PortForwarder", "SocatManager"]
