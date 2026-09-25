"""Pi (github.com/badlogic/pi-mono)'s footer contract.

Unlike Claude Code and antigravity-cli, Pi has no harness-invoked
statusline-command hook -- confirmed against its own docs
(docs/extensions.md, docs/tui.md): the footer is an in-process
TypeScript callback (`ctx.ui.setFooter()`), not something Pi calls out to
with JSON on stdin. So nothing here gets invoked by Pi itself. Instead a
thin extension (`pi-extension.ts` in this repo, symlinked into
`~/.pi/agent/extensions/` by `install_pi()`) gathers what it can see
in-process and pipes it to `bin/pi-statusline` on stdin -- the same
JSON-on-stdin contract every other adapter uses, just harness-side
instead of Pi-invoked. See CONTRIBUTING.md and `pi-extension.ts` for the
full wiring.

Schema (fields this adapter reads -- all supplied by our own extension,
not by Pi itself):
  cwd
  branch
  model.id, model.provider
  context_window.used_percentage
  tokens.input, tokens.output, tokens.cost
  session_id

Segment names (for a ~/.config/omniline/config.json "pi" section -- see
omniline/config.py): account, path, model, context, tokens, edgentic.
"context" honors style overrides label/warn_pct/danger_pct/width. Pi has
no documented rate-limit/quota payload the way Claude Code and
antigravity-cli do, so there's no five_hour/seven_day/quota segment here.
"""
from .. import config, render
from ..sources import clauth, edgentic, git
from . import base

DEFAULT_ORDER = ["account", "path", "model", "context", "tokens", "edgentic"]


def _fmt_count(n):
    return str(n) if n < 1000 else f"{n / 1000:.1f}k"


def _tokens_segment(tokens_obj):
    if not isinstance(tokens_obj, dict):
        return ""
    input_tokens = tokens_obj.get("input") or 0
    output_tokens = tokens_obj.get("output") or 0
    cost = tokens_obj.get("cost") or 0
    if not input_tokens and not output_tokens:
        return ""
    seg = (
        f"{render.DIM}↑{render.RESET}{_fmt_count(input_tokens)} "
        f"{render.DIM}↓{render.RESET}{_fmt_count(output_tokens)}"
    )
    if cost:
        seg += f" {render.DIM}${cost:.3f}{render.RESET}"
    return seg


def main():
    payload = base.read_payload()
    cfg = config.load()
    section = config.harness_section(cfg, "pi")
    segments = {}

    cwd = payload.get("cwd") or "."

    account = clauth.get_account()
    chip = clauth.render_chip(account)
    if chip:
        segments["account"] = chip

    branch = payload.get("branch") or git.get_branch(cwd)
    loc = f"{render.CYAN}{base.display_dir(cwd)}{render.RESET}"
    if branch:
        loc += f"{render.DIM}:{render.RESET}{render.WHITE}{branch}{render.RESET}"
    segments["path"] = loc

    model_obj = payload.get("model")
    if not isinstance(model_obj, dict):
        model_obj = {}
    model_name = model_obj.get("id") or "no-model"
    segments["model"] = f"{render.BLUE}{model_name}{render.RESET}"

    context_obj = payload.get("context_window")
    if isinstance(context_obj, dict) and context_obj.get("used_percentage") is not None:
        style = config.segment_style(section, "context")
        label = config.style_str(style, "label", "ctx")
        warn = config.style_num(style, "warn_pct", 50)
        danger = config.style_num(style, "danger_pct", 80)
        width = config.style_num(style, "width", 4)
        segments["context"] = render.meter(
            label, context_obj["used_percentage"], width=width, warn=warn, danger=danger
        )

    segments["tokens"] = _tokens_segment(payload.get("tokens"))

    chip = edgentic.render_chip(payload)
    if chip:
        segments["edgentic"] = chip

    template = config.resolve_template(section, DEFAULT_ORDER)
    print(config.render_template(template, segments))
