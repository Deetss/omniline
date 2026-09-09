"""Claude Code's statusLine JSON contract.

Wired up via ~/.claude/settings.json (statusLine.command) ->
~/.claude/statusline-command.sh -> bin/claude-statusline in this repo.

Schema (fields this adapter actually reads):
  workspace.current_dir  or  cwd
  model.display_name  or  model.id
  context_window.used_percentage
  rate_limits.five_hour.{used_percentage,resets_at}
  rate_limits.seven_day.{used_percentage,resets_at}
  vcs.branch  or  worktree.branch          (falls back to `git` in cwd)
  vim.mode
  session_id
  background_tasks, subagents              (lists; only their length is used)

Segment names (for a ~/.config/omniline/config.json "claude_code" section --
see omniline/config.py): account, path, model, context, five_hour,
seven_day, edgentic, vim, background_tasks, subagents. "context" honors
style overrides label/warn_pct/danger_pct/width; five_hour/seven_day honor
label only -- their coloring is burn-rate-aware (see pace.py), not a plain
threshold, so warn_pct/danger_pct don't apply to them.
"""
from .. import config, render
from ..pace import (
    FIVE_HOUR_WINDOW_MIN,
    SEVEN_DAY_WINDOW_MIN,
    format_countdown,
    mins_until,
    pace_color,
    pace_target_pct,
)
from ..sources import clauth, edgentic, git
from . import base

DEFAULT_ORDER = [
    "account", "path", "model", "context", "five_hour", "seven_day",
    "edgentic", "vim", "background_tasks", "subagents",
]


def _rate_limit_segment(name, default_label, data, window, account, style):
    if not isinstance(data, dict) or data.get("used_percentage") is None:
        return ""
    used = data["used_percentage"]
    mins_left = mins_until(data.get("resets_at"))
    color = pace_color(used, mins_left, window)
    label = config.style_str(style, "label", default_label)
    seg = render.meter(label, used, color)
    target = pace_target_pct(mins_left, window)
    if target is not None:
        seg += f" {color}({target:.1f}%){render.RESET}"
    if name == "seven_day":
        # Weekly slice of the seat price the bar maps to. Personal is Pro
        # ($20/mo); work is Max ($200/mo) -- the only two clauth profiles.
        plan_price = 20 if account == "personal" else 200
        weekly_price = plan_price * 12 / 52
        effective = used * weekly_price / 100
        seg += f" {color}${effective:.0f}{render.DIM}/${weekly_price:.0f}{render.RESET}"
    seg += format_countdown(mins_left)
    return seg


def main():
    payload = base.read_payload()
    cfg = config.load()
    section = config.harness_section(cfg, "claude_code")
    segments = {}

    workspace_obj = payload.get("workspace")
    cwd = (
        (isinstance(workspace_obj, dict) and workspace_obj.get("current_dir"))
        or payload.get("cwd")
        or "."
    )

    # Active account -- always available for the "path" segment's own use
    # below, and rendered as its own segment when there's something to show.
    account = clauth.get_account()
    chip = clauth.render_chip(account)
    if chip:
        segments["account"] = chip

    vcs_obj = payload.get("vcs")
    worktree_obj = payload.get("worktree")
    branch = (
        (isinstance(vcs_obj, dict) and vcs_obj.get("branch"))
        or (isinstance(worktree_obj, dict) and worktree_obj.get("branch"))
        or git.get_branch(cwd)
    )
    loc = f"{render.CYAN}{base.display_dir(cwd)}{render.RESET}"
    if branch:
        loc += f"{render.DIM}:{render.RESET}{render.WHITE}{branch}{render.RESET}"
    segments["path"] = loc

    model_obj = payload.get("model")
    if not isinstance(model_obj, dict):
        model_obj = {}
    model_name = model_obj.get("display_name") or model_obj.get("id") or "AGY"
    if " (" in model_name:
        model_name = model_name.split(" (")[0]
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

    rate_limits = payload.get("rate_limits")
    if isinstance(rate_limits, dict):
        segments["five_hour"] = _rate_limit_segment(
            "five_hour", "5h", rate_limits.get("five_hour"), FIVE_HOUR_WINDOW_MIN,
            account, config.segment_style(section, "five_hour"),
        )
        segments["seven_day"] = _rate_limit_segment(
            "seven_day", "7d", rate_limits.get("seven_day"), SEVEN_DAY_WINDOW_MIN,
            account, config.segment_style(section, "seven_day"),
        )

    chip = edgentic.render_chip(payload)
    if chip:
        segments["edgentic"] = chip

    vim_obj = payload.get("vim")
    if isinstance(vim_obj, dict) and vim_obj.get("mode"):
        segments["vim"] = f"{render.YELLOW}{vim_obj['mode']}{render.RESET}"

    bg_tasks = payload.get("background_tasks")
    if isinstance(bg_tasks, list) and bg_tasks:
        segments["background_tasks"] = f"{render.DIM}bg:{len(bg_tasks)}{render.RESET}"
    subagents = payload.get("subagents")
    if isinstance(subagents, list) and subagents:
        segments["subagents"] = f"{render.DIM}sub:{len(subagents)}{render.RESET}"

    template = config.resolve_template(section, DEFAULT_ORDER)
    print(config.render_template(template, segments))
