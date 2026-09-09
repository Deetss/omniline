"""antigravity-cli's statusline JSON contract, confirmed via
https://antigravity.google/docs/cli/statusline (fetched 2026-09-09).

antigravity-cli was not actually installed/runnable on the machine this was
written on -- the CLI binary wasn't on PATH, only a settings.json from an
earlier, unrelated setup. So this is built from the documented schema, not
from an observed real payload. In particular `quota` uses dynamic
"[model/bucket_id]" keys with no example strings given, so the rendering
below treats every bucket generically rather than assuming names like
Claude Code's fixed "five_hour"/"seven_day" -- verify the label formatting
against real output the first time this actually runs.

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
"""
import time
from datetime import datetime

from .. import render
from ..pace import format_countdown
from ..sources import clauth, edgentic, git
from . import base


def _mins_until_iso(reset_time):
    try:
        dt = datetime.fromisoformat(reset_time.replace("Z", "+00:00"))
        return int((dt.timestamp() - time.time()) // 60)
    except Exception:
        return None


def _quota_segments(parts, quota_obj):
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
        parts.append(seg)


def main():
    payload = base.read_payload()
    parts = []

    workspace_obj = payload.get("workspace")
    cwd = (
        (isinstance(workspace_obj, dict) and workspace_obj.get("current_dir"))
        or payload.get("cwd")
        or "."
    )

    # 1. Active account -- lead with it so billing is unmistakable.
    account = clauth.get_account()
    chip = clauth.render_chip(account)
    if chip:
        parts.append(chip)

    # 2. Path, branch, and dirty marker
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
    parts.append(loc)

    # 3. Model
    model_obj = payload.get("model")
    if not isinstance(model_obj, dict):
        model_obj = {}
    model_name = model_obj.get("display_name") or model_obj.get("id") or "AGY"
    parts.append(f"{render.BLUE}{model_name}{render.RESET}")

    # 4. Context window
    context_obj = payload.get("context_window")
    if isinstance(context_obj, dict) and context_obj.get("used_percentage") is not None:
        parts.append(render.meter("ctx", context_obj["used_percentage"]))

    # 5. Quota buckets (dynamic keys, rendered generically)
    quota_obj = payload.get("quota")
    if isinstance(quota_obj, dict):
        _quota_segments(parts, quota_obj)

    # 6. Local tokens (edgentic log)
    chip = edgentic.render_chip(payload)
    if chip:
        parts.append(chip)

    # 7. Vim mode
    vim_obj = payload.get("vim")
    if isinstance(vim_obj, dict) and vim_obj.get("mode"):
        parts.append(f"{render.YELLOW}{vim_obj['mode']}{render.RESET}")

    print(render.join_segments(parts))
