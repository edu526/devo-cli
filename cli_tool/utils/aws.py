import subprocess

import click


def check_aws_cli() -> bool:
    """Check if AWS CLI is installed (does not check credentials)"""
    try:
        # Check if AWS CLI is installed
        version_result = subprocess.run(
            ["aws", "--version"], capture_output=True, text=True, timeout=5
        )
        if version_result.returncode != 0:
            click.echo(
                "❌ AWS CLI is not installed. Please install it first.", err=True
            )
            return False

        return True
    except FileNotFoundError:
        click.echo("❌ AWS CLI is not installed. Please install it first.", err=True)
        return False
    except Exception as e:
        click.echo(f"❌ Error checking AWS CLI: {str(e)}", err=True)
        return False
