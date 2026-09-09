"""Shared adapter helpers. An adapter's whole job: read stdin JSON, map
that harness's own field names onto render/pace/sources calls, print
render.join_segments(parts). Everything schema-specific belongs in the
adapter module, not here.
"""
import json
import os
import sys


def read_payload():
    try:
        payload = json.load(sys.stdin)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def display_dir(cwd):
    home = os.path.expanduser("~")
    if cwd == home:
        return "~"
    return os.path.basename(cwd) if cwd != "/" else "/"
