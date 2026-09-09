"""Current branch for a directory, when the harness doesn't already hand
one over in its payload (Claude Code's vcs/worktree fields take priority
over this in the adapter; this is the universal fallback)."""
import subprocess


def get_branch(cwd):
    try:
        return subprocess.check_output(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return ""
