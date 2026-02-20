from jinja2 import Environment, FileSystemLoader

from cli_tool.config import TEMPLATES_DIR


def render_template(template_name: str, **kwargs) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template(template_name)
    return template.render(**kwargs)
