"""ANSI rendering primitives shared by every harness adapter. Pure
functions, no I/O — adapters own reading stdin and printing the result.
"""

RESET = "\033[0m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
WHITE = "\033[97m"
MAGENTA = "\033[35m"


def make_bar(pct, length=4):
    try:
        pct = float(pct)
    except (ValueError, TypeError):
        pct = 0.0
    filled = min(int(round(pct * length / 100)), length)
    return ("█" * filled) + ("░" * (length - filled))


def pct_color(pct, warn=50, danger=80):
    try:
        pct = float(pct)
    except (ValueError, TypeError):
        pct = 0.0
    if pct >= danger:
        return RED
    if pct >= warn:
        return YELLOW
    return GREEN


def meter(label, pct, color=None, width=4, warn=50, danger=80):
    """A `label` + bar + percentage segment, e.g. `ctx██░░34%`."""
    try:
        pct_val = float(pct)
    except (ValueError, TypeError):
        pct_val = 0.0
    color = color or pct_color(pct_val, warn, danger)
    return f"{DIM}{label}{RESET}{color}{make_bar(pct_val, width)}{RESET}{WHITE}{int(pct_val)}%{RESET}"
