"""EventBridge rules management logic."""

from typing import Dict, List, Optional

from botocore.exceptions import ClientError

from cli_tool.core.utils.aws import create_aws_client


class RulesManager:
    """Manages EventBridge rules operations."""

    def __init__(self, profile: str, region: str = "us-east-1"):
        """Initialize rules manager.

        Args:
          profile: AWS profile name
          region: AWS region
        """
        self.profile = profile
        self.region = region
        self.client = create_aws_client("events", profile_name=profile, region_name=region)

    def get_all_rules(self) -> List[Dict]:
        """Fetch all EventBridge rules.

        Returns:
          List of rule dictionaries
        """
        paginator = self.client.get_paginator("list_rules")
        all_rules = []

        for page in paginator.paginate():
            all_rules.extend(page["Rules"])

        return all_rules

    def get_rule_targets(self, rule_name: str) -> List[Dict]:
        """Get targets for a specific rule.

        Args:
          rule_name: Name of the rule

        Returns:
          List of target dictionaries
        """
        try:
            response = self.client.list_targets_by_rule(Rule=rule_name)
            return response.get("Targets", [])
        except ClientError:
            return []

    def get_rule_tags(self, rule_arn: str) -> Dict[str, str]:
        """Get tags for a specific rule.

        Args:
          rule_arn: ARN of the rule

        Returns:
          Dictionary of tag key-value pairs
        """
        try:
            response = self.client.list_tags_for_resource(ResourceARN=rule_arn)
            return {tag["Key"]: tag["Value"] for tag in response.get("Tags", [])}
        except ClientError:
            return {}

    def get_filtered_rules(self, env: Optional[str] = None, status: str = "ALL") -> List[Dict]:
        """Get rules with filtering applied.

        Args:
          env: Environment filter (e.g., dev, staging, prod)
          status: Status filter (ENABLED, DISABLED, ALL)

        Returns:
          List of filtered rule dictionaries with targets and tags
        """
        all_rules = self.get_all_rules()

        if not all_rules:
            return []

        filtered_rules = []

        for rule in all_rules:
            # Filter by status
            if status != "ALL" and rule["State"] != status:
                continue

            # Get rule details
            rule_name = rule["Name"]
            rule_arn = rule["Arn"]

            targets = self.get_rule_targets(rule_name)
            tags = self.get_rule_tags(rule_arn)

            # Filter by environment if specified
            if env and not self._matches_environment(env, targets, tags):
                continue

            # Add to filtered list
            filtered_rules.append({"rule": rule, "targets": targets, "tags": tags})

        return filtered_rules

    def _matches_environment(self, env: str, targets: List[Dict], tags: Dict[str, str]) -> bool:
        """Check if rule matches the specified environment.

        Args:
          env: Environment to match
          targets: List of rule targets
          tags: Rule tags

        Returns:
          True if rule matches environment
        """
        # Check environment tag
        env_from_tag = tags.get("Env", tags.get("Environment", "")).lower()
        if env_from_tag == env.lower():
            return True

        # Check target ARNs for environment patterns
        for target in targets:
            target_arn = target.get("Arn", "")

            # Check simple patterns
            if f"service-{env}-" in target_arn.lower() or f"-{env}-lambda" in target_arn.lower():
                return True

            # Extract from Lambda function name pattern
            if ":function:" in target_arn:
                func_name = target_arn.split(":function:")[-1].split(":")[0]
                parts = func_name.split("-")

                for part in parts:
                    if part.lower() == env.lower():
                        return True

        return False
