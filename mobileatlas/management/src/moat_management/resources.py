from contextlib import contextmanager
from datetime import timedelta
from importlib.resources import as_file, files
from pathlib import Path

from fastapi.templating import Jinja2Templates

_TEMPLATES: Jinja2Templates | None = None

_STATIC: Path | None = None


def format_timedelta(td: timedelta, fmt="{hours:02}:{m:02}:{s:02}") -> str:
    args = {}
    args["weeks"] = td // timedelta(weeks=1)
    args["days"] = td // timedelta(days=1)
    args["hours"] = td // timedelta(hours=1)
    args["minutes"] = td // timedelta(minutes=1)
    args["seconds"] = td // timedelta(seconds=1)
    args["milliseconds"] = td // timedelta(milliseconds=1)
    args["microseconds"] = td // timedelta(microseconds=1)

    args["s"] = args["seconds"] % 60
    args["m"] = args["minutes"] % 60

    return fmt.format(**args)


@contextmanager
def templates():
    global _TEMPLATES

    template_path = files("moat_management").joinpath("templates")
    with as_file(template_path) as p:
        _TEMPLATES = Jinja2Templates(directory=p)
        _TEMPLATES.env.filters["format_timedelta"] = format_timedelta
        yield
        _TEMPLATES = None


@contextmanager
def static():
    global _STATIC

    static_path = files("moat_management").joinpath("static")
    with as_file(static_path) as p:
        _STATIC = p
        yield _STATIC
        _STATIC = None


def get_templates() -> Jinja2Templates:
    if _TEMPLATES is None:
        raise AssertionError("Template resource was not initialized.")

    return _TEMPLATES
