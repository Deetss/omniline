"""UNREACHABLE by design, not just unfinished -- confirmed against Codex's
own source (codex-rs/tui/src/bottom_pane/status_line_setup.rs, 2026-09-09):
Codex's statusline only accepts a fixed, kebab-case identifier list
(`StatusLineItem` enum -- current-dir, git-branch, five-hour-limit, etc.)
under `[tui]` / `status_line` in ~/.codex/config.toml. There is no
custom-command hook, so nothing can ever pipe JSON into a script here.
See openai/codex#17827 -- this is a widely-requested feature, not shipped.

"Installing" Codex support therefore isn't an adapter at all: it's
installer.install_codex() writing that native config directly. This module
and bin/codex-statusline exist only so the adapter list stays uniform and
so a `bin/codex-statusline` invocation fails safe (no-op) instead of
crashing, in case Codex ever does add a real hook and someone wires this up
speculatively.

If Codex ever ships a real hook: read its stdin JSON in main() below, map
its field names onto omniline.render / .pace / .sources calls into a
`segments` dict the same way adapters/claude_code.py does, then resolve
and print a template via omniline.config.
"""
from . import base


def main():
    base.read_payload()
    # No hook to render for -- see module docstring. Print nothing so this
    # is a harmless no-op rather than a crash or garbage output.
