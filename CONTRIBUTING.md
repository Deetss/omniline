# Contributing

## Adding a harness

1. Confirm the harness actually supports executing a custom command with
   JSON on stdin — check its own docs/source, don't assume. If it only
   supports fixed built-in fields (like Codex), it needs `install_*` /
   `uninstall_*` functions in `installer.py` instead of an adapter.
2. Capture a real payload sample if you can. Don't guess at field names —
   see `adapters/antigravity.py`'s docstring for what an earlier guess
   (wrong key names, entirely fictional shape) cost this repo once already.
3. Write `omniline/adapters/<harness>.py`: read the payload with
   `base.read_payload()`, pull out whatever fields exist, build up a named
   `segments` dict using `render.meter()` / `pace.pace_color()` /
   `sources.*`, then resolve and print a template via
   `config.resolve_template()` / `config.render_template()` (see
   `adapters/claude_code.py` for the pattern, and the README's
   "Customizing your statusline" section for what a template is). Only put
   a key in `segments` when the data for it is actually present — a
   harness that doesn't send rate limits should just not have a
   rate-limit segment, not crash or show zeros. Document each segment's
   name in the adapter's module docstring so users know what they can put
   in a template.
4. Add `bin/<harness>-statusline` (copy `bin/claude-statusline`, swap the
   import).
5. Add status/install/uninstall functions to `installer.py`, using
   `home_dir()` for every path (not `os.path.expanduser` directly) so it
   stays testable, and register it in `COMMAND_HARNESSES` (or alongside
   Codex's handling in `main()`/`uninstall_main()` if it's a fixed-identifier
   harness rather than a custom command).
6. Add its install/uninstall/restore cases to `tests/test_installer.py`, and
   (if it reads `~/.config/omniline/config.json`) any new config-parsing
   behavior to `tests/test_config.py`.

If you're opening a PR for a new harness rather than working from an issue,
use the `harness_support` issue template as your checklist — it captures the
same "confirmed, not assumed" evidence maintainers will ask for anyway.

## Testing

```bash
python3 -m pytest tests/
```

`tests/test_installer.py` exercises install -> backup -> uninstall ->
restore for every harness against a fake `$HOME`. `tests/test_config.py`
covers config loading (missing/malformed files must degrade to defaults)
and `$name`-token template rendering.

To try a single adapter change by hand:

```bash
echo '{"cwd":"'"$PWD"'","model":{"display_name":"Sonnet 5"},"context_window":{"used_percentage":34}}' \
  | python3 bin/claude-statusline
```
