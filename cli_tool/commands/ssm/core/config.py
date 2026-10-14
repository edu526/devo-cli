"""SSM configuration management"""

import json
from pathlib import Path
from typing import Dict, Optional

from cli_tool.commands.ssm.core.hostname_forwarding import KEY as hostname_forwarding_key
from cli_tool.core.utils.config_manager import load_config, save_config


class SSMConfigManager:
    """Manages SSM connection configurations using consolidated config."""

    def load(self) -> Dict:
        """Load SSM configuration from consolidated config."""
        config = load_config()
        return config.get("ssm", {"databases": {}, "instances": {}})

    def save(self, ssm_config: Dict):
        """Save SSM configuration to consolidated config."""
        config = load_config()
        config["ssm"] = ssm_config
        save_config(config)

    def add_database(
        self,
        name: str,
        bastion: str,
        host: str,
        port: int,
        region: str = "us-east-1",
        profile: Optional[str] = None,
        local_port: Optional[int] = None,
        local_address: str = "127.0.0.1",
        hostname_forwarding: Optional[bool] = None,
    ):
        """Add a database configuration"""
        config = self.load()

        if "databases" not in config:
            config["databases"] = {}

        config["databases"][name] = {
            "bastion": bastion,
            "host": host,
            "port": port,
            "region": region,
            "profile": profile,
            "local_port": local_port or port,
            "local_address": local_address,
        }
        if hostname_forwarding is not None:  # an exception to the all-databases setting
            config["databases"][name][hostname_forwarding_key] = hostname_forwarding

        self.save(config)

    def set_hostname_forwarding(self, enabled: bool, name: Optional[str] = None):
        """Turn hostname forwarding on/off for every database, or for `name`.

        Only stores the setting: the hosts file is updated by the caller.
        For every database it also drops the per-database exceptions ("all"
        means all). For one, it stores an exception, unless it matches the
        all-databases setting.
        """
        config = self.load()
        databases = config.get("databases", {})
        if name is None:
            if enabled:
                config.pop(hostname_forwarding_key, None)  # on is the default
            else:
                config[hostname_forwarding_key] = False
            for db in databases.values():
                db.pop(hostname_forwarding_key, None)
        else:
            db = databases.get(name)
            if db is None:
                raise KeyError(f"Database '{name}' not configured")
            if enabled == (config.get(hostname_forwarding_key, True) is not False):
                db.pop(hostname_forwarding_key, None)
            else:
                db[hostname_forwarding_key] = enabled
        self.save(config)

    def remove_database(self, name: str) -> bool:
        """Remove a database configuration"""
        config = self.load()

        if name in config.get("databases", {}):
            del config["databases"][name]
            self.save(config)
            return True

        return False

    def get_database(self, name: str) -> Optional[Dict]:
        """Get a database configuration by name"""
        config = self.load()
        return config.get("databases", {}).get(name)

    def list_databases(self) -> Dict:
        """List all database configurations"""
        config = self.load()
        return config.get("databases", {})

    def add_instance(self, name: str, instance_id: str, region: str = "us-east-1", profile: Optional[str] = None):
        """Add an instance configuration"""
        config = self.load()

        if "instances" not in config:
            config["instances"] = {}

        config["instances"][name] = {"instance_id": instance_id, "region": region, "profile": profile}

        self.save(config)

    def remove_instance(self, name: str) -> bool:
        """Remove an instance configuration"""
        config = self.load()

        if name in config.get("instances", {}):
            del config["instances"][name]
            self.save(config)
            return True

        return False

    def get_instance(self, name: str) -> Optional[Dict]:
        """Get an instance configuration by name"""
        config = self.load()
        return config.get("instances", {}).get(name)

    def list_instances(self) -> Dict:
        """List all instance configurations"""
        config = self.load()
        return config.get("instances", {})

    def export_config(self, output_path: str):
        """Export configuration to a file"""
        config = self.load()
        output = Path(output_path)

        with open(output, "w") as f:
            json.dump(config, f, indent=2)

    def import_config(self, input_path: str, merge: bool = False):
        """Import configuration from a file"""
        input_file = Path(input_path)

        if not input_file.exists():
            raise FileNotFoundError(f"Config file not found: {input_path}")

        with open(input_file, "r") as f:
            imported_config = json.load(f)

        if merge:
            current_config = self.load()
            # Merge databases
            if "databases" in imported_config:
                current_config.setdefault("databases", {}).update(imported_config["databases"])
            # Merge instances
            if "instances" in imported_config:
                current_config.setdefault("instances", {}).update(imported_config["instances"])
            self.save(current_config)
        else:
            self.save(imported_config)
