---
name: Harness support request
about: Ask for a new AI coding CLI to get an omniline adapter
title: "Support <harness name>"
labels: new-harness
---

omniline only adds a harness once its statusline hook is **confirmed, not
assumed**. This repo has been burned by a guessed schema before (a `quota`
shape invented from a vague description, wired in, and simply wrong) —
see `omniline/adapters/antigravity.py`'s docstring and the README's
"Why split it this way" section for that history. Please fill in both
sections below; a request without them will most likely just get asked to
come back with this evidence.

**Harness name**

**1. Proof it supports a custom statusline command with JSON on stdin**

Link the harness's own docs or source that show it can:
- invoke an arbitrary external command on prompt render, and
- feed that command a JSON payload on stdin (not just display a fixed set
  of built-in fields)

A harness having "a statusline" at all is not enough — Codex has one and
still can't be adapted, because it only accepts a fixed field list, not a
command. See the Codex row in the README's per-harness table for what that
looks like when the answer is no.

Link:

**2. A captured real payload sample**

Paste an actual JSON payload this harness sent on stdin (redact anything
sensitive — paths, session ids, tokens). Not a payload reconstructed from
docs, and not one you're guessing at from field names you've seen mentioned
elsewhere — the real bytes the harness wrote, ideally captured with
something like `cat > /tmp/payload.json` wired in as a temporary statusline
command.

```json
paste here
```

**Anything else worth knowing**
(quirks in how the harness resolves the command, whether it re-invokes per
keystroke vs. per prompt, etc.)
