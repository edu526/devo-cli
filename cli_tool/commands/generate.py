import os

import click

from cli_tool.config import OUTPUT_DIR
from cli_tool.utils.templates import render_template


@click.command()
@click.argument("name")
def generate(name):
    """Generates a file based on a template."""
    content = render_template("ejemplo_template.txt.j2", name=name)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{name}.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    click.echo(f"✅ File generated at {output_path}")
