"""antigravity-cli's statusline JSON contract, confirmed via
https://antigravity.google/docs/cli/statusline (fetched 2026-09-09).

Built from the documented schema before a live antigravity-cli was
available to test against; verified working against a real install and
real payload on 2026-09-09. `quota` uses dynamic "[model/bucket_id]" keys
with no example strings in the docs, so the rendering below treats every
bucket generically rather than assuming names like Claude Code's fixed
"five_hour"/"seven_day" -- confirmed correct against real bucket ids
(e.g. 3rd-party and Gemini 5h/weekly windows).

Wired up via antigravity-cli's own settings.json (statusLine.command), set
either with the `/statusline <path>` slash command inside antigravity-cli or
by editing settings.json directly -- see bin/install.

Schema (fields this adapter reads):
  workspace.current_dir  or  cwd
  model.display_name  or  model.id
  context_window.used_percentage
  quota.<bucket_id>.{remaining_fraction, reset_in_seconds, reset_time (ISO 8601)}
  vcs.branch, vcs.dirty                    (falls back to `git` in cwd)
  vim.mode
  session_id

Segment names (for a ~/.config/omniline/config.json "antigravity" section --
see omniline/config.py): account, path, model, context, quota, edgentic,
vim. "context" honors style overrides label/warn_pct/danger_pct/width.
"quota" is a single combined segment (every bucket rendered generically,
in payload order) since bucket ids are dynamic and can't be named
individually in a template ahead of time.
"""
import time
from datetime import datetime

from .. import config, render
from ..pace import format_countdown
from ..sources import clauth, edgentic, git
from . import base

DEFAULT_ORDER = ["account", "path", "model", "context", "quota", "edgentic", "vim"]


def _mins_until_iso(reset_time):
    try:
        dt = datetime.fromisoformat(reset_time.replace("Z", "+00:00"))
        return int((dt.timestamp() - time.time()) // 60)
    except Exception:
        return None


def _quota_segment(quota_obj):
    bucket_segs = []
    for bucket_id, data in sorted(quota_obj.items()):
        if not isinstance(data, dict) or data.get("remaining_fraction") is None:
            continue
        pct = (1.0 - data["remaining_fraction"]) * 100
        label = bucket_id.rsplit("/", 1)[-1][:8]

        mins_left = None
        seconds = data.get("reset_in_seconds")
        if seconds is not None:
            mins_left = int(seconds) // 60
        elif data.get("reset_time"):
            mins_left = _mins_until_iso(data["reset_time"])

        seg = render.meter(label, pct)
        seg += format_countdown(mins_left)
        bucket_segs.append(seg)
    return f"{render.DIM} · {render.RESET}".join(bucket_segs)


def main():
    payload = base.read_payload()
    cfg = config.load()
    section = config.harness_section(cfg, "antigravity")
    segments = {}

    workspace_obj = payload.get("workspace")
    cwd = (
        (isinstance(workspace_obj, dict) and workspace_obj.get("current_dir"))
        or payload.get("cwd")
        or "."
    )

    account = clauth.get_account()
    chip = clauth.render_chip(account)
    if chip:
        segments["account"] = chip

    vcs_obj = payload.get("vcs")
    branch = None
    dirty = False
    if isinstance(vcs_obj, dict):
        branch = vcs_obj.get("branch")
        dirty = bool(vcs_obj.get("dirty"))
    if not branch:
        branch = git.get_branch(cwd)
    loc = f"{render.CYAN}{base.display_dir(cwd)}{render.RESET}"
    if branch:
        loc += f"{render.DIM}:{render.RESET}{render.WHITE}{branch}{render.RESET}"
        if dirty:
            loc += f"{render.YELLOW}*{render.RESET}"
    segments["path"] = loc

    model_obj = payload.get("model")
    if not isinstance(model_obj, dict):
        model_obj = {}
    model_name = model_obj.get("display_name") or model_obj.get("id") or "AGY"
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

    quota_obj = payload.get("quota")
    if isinstance(quota_obj, dict):
        segments["quota"] = _quota_segment(quota_obj)

    chip = edgentic.render_chip(payload)
    if chip:
        segments["edgentic"] = chip

    vim_obj = payload.get("vim")
    if isinstance(vim_obj, dict) and vim_obj.get("mode"):
        segments["vim"] = f"{render.YELLOW}{vim_obj['mode']}{render.RESET}"

    template = config.resolve_template(section, DEFAULT_ORDER)
    print(config.render_template(template, segments))
