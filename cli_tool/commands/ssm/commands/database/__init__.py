"""Database connection commands for SSM."""

from cli_tool.commands.ssm.commands.database.add import add_database
from cli_tool.commands.ssm.commands.database.connect import connect_database
from cli_tool.commands.ssm.commands.database.list import list_databases
from cli_tool.commands.ssm.commands.database.remove import remove_database


def register_database_commands(ssm_group):
    """Register database-related commands to the SSM group."""

    @ssm_group.group("database")
    def database():
        """Manage database connections"""
        pass

    # Register all database commands
    database.add_command(connect_database, "connect")
    database.add_command(list_databases, "list")
    database.add_command(add_database, "add")
    database.add_command(remove_database, "remove")
