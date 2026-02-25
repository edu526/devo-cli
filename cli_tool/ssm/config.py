"""SSM configuration management"""

import json
from pathlib import Path
from typing import Dict, Optional


class SSMConfigManager:
    """Manages SSM connection configurations"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Default: ~/.devo/ssm-config.json
            self.config_path = Path.home() / ".devo" / "ssm-config.json"

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict:
        """Load SSM configuration from file"""
        if not self.config_path.exists():
            return {"databases": {}, "instances": {}}

        with open(self.config_path, "r") as f:
            return json.load(f)

    def save(self, config: Dict):
        """Save SSM configuration to file"""
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

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
