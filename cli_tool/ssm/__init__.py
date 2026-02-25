"""AWS Systems Manager Session Manager integration"""

from cli_tool.ssm.config import SSMConfigManager
from cli_tool.ssm.hosts_manager import HostsManager
from cli_tool.ssm.port_forwarder import PortForwarder
from cli_tool.ssm.session import SSMSession

# Backward compatibility
SocatManager = PortForwarder

__all__ = ["SSMConfigManager", "SSMSession", "HostsManager", "PortForwarder", "SocatManager"]
