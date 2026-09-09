"""Active clauth (github.com/uwuclxdy/clauth) account. Reflects whichever
profile actually owns the loaded credentials right now, via `clauth which`
— not which launcher alias started the shell, which can go stale the moment
someone switches profiles mid-session.

Any harness clauth manages accounts for can use this unchanged.
"""
import json
import subprocess

from ..render import BLUE, GREEN, MAGENTA, RESET

_LABELS = {"work": "wrk", "personal": "prs"}
_COLORS = {"work": BLUE, "personal": GREEN}


def get_account():
    try:
        out = subprocess.run(
            ["clauth", "which", "--json"],
            capture_output=True, text=True, timeout=1,
        )
        if out.returncode != 0:
            return None
        profile = json.loads(out.stdout).get("profile")
        return profile if profile and profile != "unknown" else None
    except Exception:
        return None


def render_chip(account):
    """`account` from get_account(); returns a colored 3-letter chip, or
    None if there's nothing to show."""
    if not account:
        return None
    color = _COLORS.get(account, MAGENTA)
    label = _LABELS.get(account, account[:3])
    return f"{color}{label}{RESET}"
