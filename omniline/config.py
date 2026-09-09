"""User-defined statusline templates and per-segment style overrides.

Config is entirely optional and lives at
$XDG_CONFIG_HOME/omniline/config.json (falling back to
~/.config/omniline/config.json). Every adapter has a built-in default
template and style, so a missing, empty, or malformed config file must
never break the statusline -- it's read best-effort, and any problem just
means "fall back to the default" instead of crashing on every prompt
render.

Shape:
  {
    "<harness>": {
      "template": "$account · $path · $model",   // raw Starship-style
                                                    // template: full control
                                                    // over literal text and
                                                    // separators.
      "segments": ["account", "path", "model"],   // OR: just the order/
                                                    // subset to show, with
                                                    // the framework's own
                                                    // separator -- ignored
                                                    // if "template" is set.
      "separator": " · ",                          // only used with
                                                    // "segments".
      "style": {
        "<segment>": {"label": "ctx", "warn_pct": 60, "danger_pct": 85, "width": 6}
      }
    }
  }

See each adapter's module docstring for its available segment names.
"""
import json
import os
import re

from .render import DIM, RESET

_TOKEN_RE = re.compile(r"\$(\w+)")


def _config_home():
    test_home = os.environ.get("OMNILINE_TEST_HOME")
    if test_home:
        return os.path.join(test_home, ".config")
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def config_path() -> str:
    return os.path.join(_config_home(), "omniline", "config.json")


def load() -> dict:
    path = config_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def harness_section(config: dict, harness: str) -> dict:
    """This harness's config sub-dict, or {} -- callers apply their own
    per-key defaults on top of whatever this returns."""
    section = config.get(harness)
    return section if isinstance(section, dict) else {}


def segment_style(section: dict, name: str) -> dict:
    style = section.get("style")
    if not isinstance(style, dict):
        return {}
    seg = style.get(name)
    return seg if isinstance(seg, dict) else {}


def style_str(style: dict, key: str, default: str) -> str:
    value = style.get(key, default)
    return value if isinstance(value, str) and value else default


def style_num(style: dict, key: str, default):
    """Reads a numeric style override, falling back to `default` (and
    keeping its type, int or float) on anything a user could plausibly
    get wrong in hand-written JSON -- a missing key, a string, a bool."""
    value = style.get(key, default)
    if isinstance(value, bool):
        return default
    try:
        return type(default)(value)
    except (TypeError, ValueError):
        return default


def resolve_template(section: dict, default_order: list) -> str:
    """The template to render with: an explicit "template" string wins
    outright; otherwise build one from "segments" (order/subset) and
    "separator", falling back to `default_order` joined with the
    framework's own dim " · "."""
    template = section.get("template")
    if isinstance(template, str) and template:
        return template

    order = section.get("segments")
    if not isinstance(order, list) or not all(isinstance(n, str) for n in order):
        order = default_order

    separator = section.get("separator")
    if not isinstance(separator, str):
        separator = " · "

    return f"{DIM}{separator}{RESET}".join(f"${name}" for name in order)


def render_template(template: str, segments: dict) -> str:
    """Expand $name tokens against `segments` (name -> rendered string, or
    absent/empty meaning "nothing to show this render").

    The literal text right before a token is treated as that token's own
    separator: when the token's value is empty, both it and the literal
    text before it are dropped, so "$account · $path" degrades to just
    the path instead of a stray leading " · " when there's no account.
    Text after the final token is always kept. An unknown token name
    (a typo, or a segment this harness doesn't send) is just empty --
    never an error.
    """
    pieces = _TOKEN_RE.split(template)
    out = []
    emitted = False
    for i in range(1, len(pieces), 2):
        value = segments.get(pieces[i]) or ""
        if value:
            if emitted:
                out.append(pieces[i - 1])
            out.append(value)
            emitted = True
    out.append(pieces[-1])
    return "".join(out)
