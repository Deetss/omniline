"""Tokens an edgentic (local-model offload) session pushed to edgentic1
instead of reading into the harness itself. Any harness that shells out to
edgentic writes the same tab-separated usage.log, so this reads it
generically rather than assuming Claude Code's session id field name.
"""
import os
import time

from ..render import DIM, GREEN, RED, RESET

_SESSION_ID_KEYS = ("session_id", "conversationId", "conversation_id")


def _log_path():
    return os.path.join(
        os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
        "edgentic", "usage.log",
    )


def render_chip(payload):
    log_path = _log_path()
    if not os.path.isfile(log_path):
        return None

    session_id = next((payload.get(k) for k in _SESSION_ID_KEYS if payload.get(k)), "")
    today = time.strftime("%Y-%m-%d")
    saved = failed = today_saved = today_failed = 0

    try:
        with open(log_path) as f:
            for line in f:
                cols = line.strip().split("\t")
                if len(cols) < 7:
                    continue
                ts, status, sid = cols[0], cols[2], cols[6]
                try:
                    delta = int(cols[4]) - int(cols[5])
                except ValueError:
                    delta = 0
                if ts.startswith(today):
                    today_saved += delta if status == "ok" else 0
                    today_failed += 0 if status == "ok" else 1
                if session_id and sid == session_id:
                    saved += delta if status == "ok" else 0
                    failed += 0 if status == "ok" else 1
    except Exception:
        return None

    if saved == 0 and failed == 0:
        saved, failed = today_saved, today_failed
    if saved == 0 and failed == 0:
        return None

    human = f"{saved / 1000:.1f}k" if saved >= 1000 else str(saved)
    seg = f"{DIM}loc{RESET}{GREEN}{human}{RESET}"
    if failed > 0:
        seg += f"{RED}!{failed}{RESET}"
    return seg
