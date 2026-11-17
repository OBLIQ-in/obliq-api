"""HTML templates loader for developer dashboard and client documentation."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)

KEYS_PAGE_HTML = _jinja_env.get_template("keys.html").render()
USAGE_PAGE_HTML = _jinja_env.get_template("usage.html").render()
DOCS_PAGE_HTML = _jinja_env.get_template("docs.html").render()

__all__ = ["DOCS_PAGE_HTML", "KEYS_PAGE_HTML", "TEMPLATES_DIR", "USAGE_PAGE_HTML"]
