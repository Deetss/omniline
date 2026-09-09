"""Interactive setup for the statuslines this framework can drive.

install:   detect harness -> detect existing statusline -> back it up ->
           point it at this framework (or, for Codex, write its native config).
uninstall: back up current state -> remove our statusline config.
restore:   pick a prior backup for a harness -> back up current state ->
           copy the backup back into place.

Every mutation backs up whatever it's about to overwrite first, no
exceptions -- that backup is also what makes uninstall/restore meaningful
rather than a guess at the "off" state.

Codex is not an adapter target the way Claude Code and antigravity-cli are:
it has no custom-command hook at all (confirmed against its own source,
codex-rs/tui/src/bottom_pane/status_line_setup.rs) -- only a fixed,
kebab-case identifier list under `[tui]` / `status_line` in
~/.codex/config.toml. So install/uninstall for Codex edit that native
config directly, not bin/codex-statusline (a documented, unreachable no-op).
"""
from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from dataclasses import dataclass
from typing import Callable, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def home_dir() -> str:
    """The real $HOME, unless OMNILINE_TEST_HOME points tests at a
    sandbox -- every path in this module goes through this so tests never
    touch a real config file."""
    return os.environ.get("OMNILINE_TEST_HOME") or os.path.expanduser("~")


def backup_dir() -> str:
    return os.path.join(home_dir(), ".omniline-backups") if os.environ.get("OMNILINE_TEST_HOME") \
        else os.path.join(REPO_ROOT, "backups")


CODEX_DEFAULT_ITEMS = [
    "current-dir",
    "git-branch",
    "model-with-reasoning",
    "context-used",
    "five-hour-limit",
    "weekly-limit",
]
# Confirmed via codex-rs/tui/src/bottom_pane/status_line_setup.rs (StatusLineItem enum).
CODEX_KNOWN_ITEMS = {
    "model", "model-name", "model-with-reasoning", "reasoning", "current-dir",
    "project-name", "project", "project-root", "hostname", "git-branch",
    "pull-request-number", "branch-changes", "run-state", "status",
    "permissions", "approval-mode", "approval", "context-remaining",
    "context-used", "context-usage", "five-hour-limit", "weekly-limit",
    "codex-version", "context-window-size", "used-tokens",
    "total-input-tokens", "total-output-tokens", "thread-credits",
    "estimated-thread-cost", "thread-id", "session-id", "fast-mode",
    "raw-output", "thread-name", "thread-title", "workspace-headline",
    "task-progress",
}


def ask_yes_no(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer y or n.")


def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


# --- backup / restore, shared by every harness ------------------------------

def backup_file(label: str, path: str) -> str:
    """Copy `path` into backups/<label>-<basename>.<timestamp>[-N].bak.
    `label` (the harness key) keeps this collision-free even though Claude
    Code and antigravity-cli both back up a file literally named
    settings.json. The microsecond timestamp still isn't enough on its own
    -- two backups of the same file inside one microsecond would otherwise
    silently overwrite each other instead of both existing -- so a
    collision falls back to an incrementing suffix instead of clobbering."""
    d = backup_dir()
    os.makedirs(d, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S.%f")
    base = f"{label}-{os.path.basename(path)}.{stamp}.bak"
    dest = os.path.join(d, base)
    n = 1
    while os.path.exists(dest):
        dest = os.path.join(d, f"{base}.{n}")
        n += 1
    shutil.copy2(path, dest)
    return dest


def list_backups(label: str) -> list[str]:
    """Backups for `label`, newest first."""
    d = backup_dir()
    if not os.path.isdir(d):
        return []
    prefix = f"{label}-"
    matches = [os.path.join(d, f) for f in os.listdir(d) if f.startswith(prefix)]
    return sorted(matches, reverse=True)


def restore_backup(label: str, live_path: str, backup_path: str) -> None:
    """Back up whatever's live now (so a restore is itself undoable), then
    copy `backup_path` over `live_path`."""
    if os.path.isfile(live_path):
        saved = backup_file(label, live_path)
        print(f"  backed up current state first -> {saved}")
    os.makedirs(os.path.dirname(live_path), exist_ok=True)
    shutil.copy2(backup_path, live_path)
    print(f"  restored {live_path} <- {backup_path}")


# --- Claude Code -------------------------------------------------------------

def _claude_settings_path() -> str:
    return os.path.join(home_dir(), ".claude", "settings.json")


def claude_code_status() -> dict:
    settings_path = _claude_settings_path()
    installed = which("claude") or os.path.isfile(settings_path)
    existing = None
    if os.path.isfile(settings_path):
        try:
            with open(settings_path) as f:
                existing = json.load(f).get("statusLine")
        except (OSError, json.JSONDecodeError):
            existing = "<settings.json exists but could not be parsed>"
    return {"name": "Claude Code", "installed": installed, "path": settings_path, "existing": existing}


def install_claude_code(target_command: str) -> None:
    settings_path = _claude_settings_path()
    if not os.path.isfile(settings_path):
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        settings = {}
    else:
        backup = backup_file("claude_code", settings_path)
        print(f"  backed up existing settings.json -> {backup}")
        with open(settings_path) as f:
            settings = json.load(f)

    entry = settings.get("statusLine") if isinstance(settings.get("statusLine"), dict) else {}
    entry["type"] = "command"
    entry["command"] = target_command
    settings["statusLine"] = entry

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print(f"  wrote statusLine.command = {target_command}")


def uninstall_claude_code() -> None:
    settings_path = _claude_settings_path()
    if not os.path.isfile(settings_path):
        print("  no settings.json found -- nothing to remove.")
        return
    with open(settings_path) as f:
        settings = json.load(f)
    if "statusLine" not in settings:
        print("  no statusLine configured -- nothing to remove.")
        return
    backup = backup_file("claude_code", settings_path)
    print(f"  backed up current settings.json -> {backup}")
    del settings["statusLine"]
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("  removed statusLine from settings.json")


# --- antigravity-cli ---------------------------------------------------------

def _antigravity_settings_path() -> str:
    return os.path.join(home_dir(), ".gemini", "antigravity-cli", "settings.json")


def antigravity_status() -> dict:
    settings_path = _antigravity_settings_path()
    installed = which("antigravity-cli") or which("antigravity") or os.path.isfile(settings_path)
    existing = None
    if os.path.isfile(settings_path):
        try:
            with open(settings_path) as f:
                existing = json.load(f).get("statusLine")
        except (OSError, json.JSONDecodeError):
            existing = "<settings.json exists but could not be parsed>"
    return {"name": "antigravity-cli", "installed": installed, "path": settings_path, "existing": existing}


def install_antigravity(target_command: str) -> None:
    settings_path = _antigravity_settings_path()
    if not os.path.isfile(settings_path):
        print("  no antigravity-cli settings.json found -- set the statusline from inside")
        print(f"  antigravity-cli instead: /statusline {target_command}")
        return

    backup = backup_file("antigravity", settings_path)
    print(f"  backed up existing settings.json -> {backup}")
    with open(settings_path) as f:
        settings = json.load(f)

    entry = settings.get("statusLine") if isinstance(settings.get("statusLine"), dict) else {}
    entry["type"] = "command"
    entry["command"] = target_command
    entry.setdefault("enabled", True)
    settings["statusLine"] = entry

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print(f"  wrote statusLine.command = {target_command}")


def uninstall_antigravity() -> None:
    settings_path = _antigravity_settings_path()
    if not os.path.isfile(settings_path):
        print("  no settings.json found -- nothing to remove.")
        return
    with open(settings_path) as f:
        settings = json.load(f)
    if "statusLine" not in settings:
        print("  no statusLine configured -- nothing to remove.")
        return
    backup = backup_file("antigravity", settings_path)
    print(f"  backed up current settings.json -> {backup}")
    del settings["statusLine"]
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("  removed statusLine from settings.json")


# --- Codex --------------------------------------------------------------------

_SECTION_RE = re.compile(r"(?m)^\[[^\[\]]+\]\s*$|^\[\[[^\[\]]+\]\]\s*$")


def _codex_config_path() -> str:
    return os.path.join(home_dir(), ".codex", "config.toml")


def _find_top_level_section(text: str, name: str) -> Optional[tuple[int, int]]:
    """Span of a bare `[name]` table (not `[name.sub]` or `[[name]]`), or
    None. End is the next top-level section header or EOF."""
    header = re.compile(rf"(?m)^\[{re.escape(name)}\]\s*$")
    m = header.search(text)
    if not m:
        return None
    next_m = _SECTION_RE.search(text, m.end())
    end = next_m.start() if next_m else len(text)
    return m.start(), end


def codex_status() -> dict:
    config_path = _codex_config_path()
    installed = which("codex") or os.path.isfile(config_path)
    existing = None
    if os.path.isfile(config_path):
        text = open(config_path).read()
        span = _find_top_level_section(text, "tui")
        if span:
            body = text[span[0]:span[1]]
            m = re.search(r"(?m)^\s*status_line\s*=\s*(\[[^\]]*\])", body)
            if m:
                existing = m.group(1)
            else:
                existing = "<[tui] section present, no status_line key>"
    return {"name": "Codex", "installed": installed, "path": config_path, "existing": existing}


def install_codex(items: list[str]) -> None:
    config_path = _codex_config_path()
    unknown = [i for i in items if i not in CODEX_KNOWN_ITEMS]
    if unknown:
        print(f"  unrecognized item id(s), skipping: {', '.join(unknown)}")
        items = [i for i in items if i in CODEX_KNOWN_ITEMS]
    if not items:
        print("  nothing to write.")
        return

    line = "status_line = [" + ", ".join(f'"{i}"' for i in items) + "]"

    if not os.path.isfile(config_path):
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            f.write(f"[tui]\n{line}\n")
        print(f"  created {config_path} with a new [tui] section")
        return

    backup = backup_file("codex", config_path)
    print(f"  backed up existing config.toml -> {backup}")
    text = open(config_path).read()
    span = _find_top_level_section(text, "tui")

    if span is None:
        sep = "" if text.endswith("\n") or not text else "\n"
        new_text = text + f"{sep}\n[tui]\n{line}\n"
    else:
        start, end = span
        body = text[start:end]
        existing_key = re.search(r"(?m)^\s*status_line\s*=\s*\[[^\]]*\]\s*$", body)
        if existing_key:
            # Only rewrite a simple, single-line array -- anything else
            # (multi-line, commented out, etc.) is left for a manual edit
            # so this can't mangle something it doesn't fully understand.
            new_body = body[:existing_key.start()] + line + body[existing_key.end():]
        else:
            new_body = body.rstrip("\n") + f"\n{line}\n"
        new_text = text[:start] + new_body + text[end:]

    with open(config_path, "w") as f:
        f.write(new_text)
    print(f"  wrote [tui] status_line = {items} to {config_path}")
    print("  restart Codex (or run /statusline inside it) to pick this up")


def uninstall_codex() -> None:
    config_path = _codex_config_path()
    if not os.path.isfile(config_path):
        print("  no config.toml found -- nothing to remove.")
        return
    text = open(config_path).read()
    span = _find_top_level_section(text, "tui")
    if span is None:
        print("  no [tui] section -- nothing to remove.")
        return
    start, end = span
    body = text[start:end]
    existing_key = re.search(r"(?m)^\s*status_line\s*=\s*\[[^\]]*\]\s*\n?", body)
    if not existing_key:
        print("  [tui] section has no status_line key -- nothing to remove.")
        return
    backup = backup_file("codex", config_path)
    print(f"  backed up current config.toml -> {backup}")
    new_body = body[:existing_key.start()] + body[existing_key.end():]
    new_text = text[:start] + new_body + text[end:]
    with open(config_path, "w") as f:
        f.write(new_text)
    print("  removed status_line from [tui]")


def prompt_codex_items() -> list[str]:
    print(f"  default order: {', '.join(CODEX_DEFAULT_ITEMS)}")
    if ask_yes_no("  use the default order?", default=True):
        return CODEX_DEFAULT_ITEMS
    raw = input("  enter comma-separated item ids in the order you want: ").strip()
    return [i.strip() for i in raw.split(",") if i.strip()]


# --- harness registry, and the three interactive entrypoints ----------------

@dataclass(frozen=True)
class Harness:
    label: str
    status_fn: Callable[[], dict]
    install_fn: Callable[[str], None]
    uninstall_fn: Callable[[], None]
    target: str


COMMAND_HARNESSES = [
    Harness("claude_code", claude_code_status, install_claude_code, uninstall_claude_code,
            os.path.join(REPO_ROOT, "bin", "claude-statusline")),
    Harness("antigravity", antigravity_status, install_antigravity, uninstall_antigravity,
            os.path.join(REPO_ROOT, "bin", "antigravity-statusline")),
]


def main() -> None:
    print(f"omniline installer -- repo: {REPO_ROOT}\n")

    for h in COMMAND_HARNESSES:
        info = h.status_fn()
        print(f"== {info['name']} ==")
        if not info["installed"]:
            print("  not detected, skipping.\n")
            continue

        if info["existing"]:
            print(f"  existing statusline config found: {info['existing']}")
            already_ours = (
                isinstance(info["existing"], dict)
                and info["existing"].get("type") == "command"
                and info["existing"].get("command") == h.target
            )
            if already_ours:
                print("  already pointed at this framework -- nothing to do.\n")
                continue
            if not ask_yes_no("  back it up and replace it?", default=False):
                print("  skipped.\n")
                continue
        else:
            if not ask_yes_no("  no statusline configured yet -- set one up now?", default=True):
                print("  skipped.\n")
                continue

        h.install_fn(h.target)
        print()

    # Codex: native fixed-identifier config, not a bin/ script.
    info = codex_status()
    print(f"== {info['name']} ==")
    if not info["installed"]:
        print("  not detected, skipping.\n")
    else:
        proceed = True
        if info["existing"]:
            print(f"  existing status_line found: {info['existing']}")
            proceed = ask_yes_no("  back it up and replace it?", default=False)
        else:
            proceed = ask_yes_no("  no status_line configured yet -- set one up now?", default=True)
        if not proceed:
            print("  skipped.\n")
        else:
            install_codex(prompt_codex_items())
            print()

    print("Done.")


def uninstall_main() -> None:
    print(f"omniline uninstaller -- repo: {REPO_ROOT}\n")

    for h in COMMAND_HARNESSES:
        info = h.status_fn()
        print(f"== {info['name']} ==")
        if not info["installed"]:
            print("  not detected, skipping.\n")
            continue
        if not info["existing"]:
            print("  no statusline configured -- nothing to remove.\n")
            continue
        print(f"  current: {info['existing']}")
        if not ask_yes_no("  back it up and remove it?", default=False):
            print("  skipped.\n")
            continue
        h.uninstall_fn()
        print()

    info = codex_status()
    print(f"== {info['name']} ==")
    if not info["installed"]:
        print("  not detected, skipping.\n")
    elif not info["existing"]:
        print("  no status_line configured -- nothing to remove.\n")
    else:
        print(f"  current: {info['existing']}")
        if ask_yes_no("  back it up and remove it?", default=False):
            uninstall_codex()
            print()
        else:
            print("  skipped.\n")

    print("Done.")


_RESTORE_TARGETS = {
    "claude_code": (lambda: claude_code_status()["name"], _claude_settings_path),
    "antigravity": (lambda: antigravity_status()["name"], _antigravity_settings_path),
    "codex": (lambda: codex_status()["name"], _codex_config_path),
}


def restore_main() -> None:
    print(f"omniline restore -- repo: {REPO_ROOT}\n")
    for label, (name_fn, path_fn) in _RESTORE_TARGETS.items():
        backups = list_backups(label)
        print(f"== {name_fn()} ==")
        if not backups:
            print("  no backups found.\n")
            continue
        for i, b in enumerate(backups):
            print(f"  [{i}] {os.path.basename(b)}")
        choice = input("  restore which index? (blank to skip) ").strip()
        if not choice:
            print("  skipped.\n")
            continue
        try:
            idx = int(choice)
            backup_path = backups[idx]
        except (ValueError, IndexError):
            print("  invalid choice, skipped.\n")
            continue
        restore_backup(label, path_fn(), backup_path)
        print()
    print("Done.")


if __name__ == "__main__":
    main()
