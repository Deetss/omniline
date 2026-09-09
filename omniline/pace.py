"""Burn-aware coloring for rate-limit windows (5h/7d style quotas): color
reflects whether usage is ahead of, on, or behind a linear burn rate across
the window, not just the absolute percentage. Shared across any adapter
whose harness exposes a window + reset time, regardless of field names.
"""
import time

from .render import DIM, GREEN, RED, RESET, YELLOW, pct_color

FIVE_HOUR_WINDOW_MIN = 300
SEVEN_DAY_WINDOW_MIN = 10080


def mins_until(epoch_seconds):
    if not epoch_seconds:
        return None
    return int((epoch_seconds - time.time()) // 60)


def pace_color(pct, mins_left, window):
    try:
        pct = float(pct)
    except (ValueError, TypeError):
        pct = 0.0
    if pct >= 90:
        return RED
    if mins_left is None:
        return pct_color(pct)
    if pct < 10:
        return GREEN
    elapsed = max(window - mins_left, 1)
    ratio = pct * window / (elapsed * 100)
    if ratio >= 1.2:
        return RED
    if ratio >= 0.8:
        return YELLOW
    return GREEN


def pace_target_pct(mins_left, window):
    """The usage% you'd expect at this point under even burn, shown next to
    actual usage so under/over pace reads at a glance instead of just being
    implied by color."""
    if mins_left is None:
        return None
    elapsed = max(0, min(window - mins_left, window))
    return elapsed * 100 / window


def format_countdown(mins_left):
    if mins_left is None or mins_left <= 0:
        return ""
    if mins_left >= 60:
        return f"{DIM}/{mins_left // 60}h{mins_left % 60}m{RESET}"
    return f"{DIM}/{mins_left}m{RESET}"
