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
"""
from .. import render
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


def _rate_limit_segments(parts, rate_limits, account):
    five_hour = rate_limits.get("five_hour")
    if isinstance(five_hour, dict) and five_hour.get("used_percentage") is not None:
        used = five_hour["used_percentage"]
        mins_left = mins_until(five_hour.get("resets_at"))
        color = pace_color(used, mins_left, FIVE_HOUR_WINDOW_MIN)
        seg = render.meter("5h", used, color)
        target = pace_target_pct(mins_left, FIVE_HOUR_WINDOW_MIN)
        if target is not None:
            seg += f" {color}({target:.1f}%){render.RESET}"
        seg += format_countdown(mins_left)
        parts.append(seg)

    seven_day = rate_limits.get("seven_day")
    if isinstance(seven_day, dict) and seven_day.get("used_percentage") is not None:
        used = seven_day["used_percentage"]
        mins_left = mins_until(seven_day.get("resets_at"))
        color = pace_color(used, mins_left, SEVEN_DAY_WINDOW_MIN)
        target = pace_target_pct(mins_left, SEVEN_DAY_WINDOW_MIN)
        seg = render.meter("7d", used, color)
        if target is not None:
            seg += f" {color}({target:.1f}%){render.RESET}"
        # Weekly slice of the seat price the bar maps to. Personal is Pro
        # ($20/mo); work is Max ($200/mo) -- the only two clauth profiles.
        plan_price = 20 if account == "personal" else 200
        weekly_price = plan_price * 12 / 52
        effective = used * weekly_price / 100
        seg += f" {color}${effective:.0f}{render.DIM}/${weekly_price:.0f}{render.RESET}"
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

    # 2. Path and branch
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
    parts.append(loc)

    # 3. Model
    model_obj = payload.get("model")
    if not isinstance(model_obj, dict):
        model_obj = {}
    model_name = model_obj.get("display_name") or model_obj.get("id") or "AGY"
    if " (" in model_name:
        model_name = model_name.split(" (")[0]
    parts.append(f"{render.BLUE}{model_name}{render.RESET}")

    # 4. Context window
    context_obj = payload.get("context_window")
    if isinstance(context_obj, dict) and context_obj.get("used_percentage") is not None:
        parts.append(render.meter("ctx", context_obj["used_percentage"]))

    # 5. Rate limits (5h / 7d)
    rate_limits = payload.get("rate_limits")
    if isinstance(rate_limits, dict):
        _rate_limit_segments(parts, rate_limits, account)

    # 6. Local tokens (edgentic log)
    chip = edgentic.render_chip(payload)
    if chip:
        parts.append(chip)

    # 7. Vim mode
    vim_obj = payload.get("vim")
    if isinstance(vim_obj, dict) and vim_obj.get("mode"):
        parts.append(f"{render.YELLOW}{vim_obj['mode']}{render.RESET}")

    # 8. Background tasks & subagents
    bg_tasks = payload.get("background_tasks")
    if isinstance(bg_tasks, list) and bg_tasks:
        parts.append(f"{render.DIM}bg:{len(bg_tasks)}{render.RESET}")
    subagents = payload.get("subagents")
    if isinstance(subagents, list) and subagents:
        parts.append(f"{render.DIM}sub:{len(subagents)}{render.RESET}")

    print(render.join_segments(parts))
