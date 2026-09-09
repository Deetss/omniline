#!/usr/bin/env bash
# omniline installer
#
#   curl -fsSL https://raw.githubusercontent.com/Deetss/omniline/main/install.sh | bash
#
# Fetches omniline into a persistent local directory, then hands off to its
# interactive Python installer (which detects installed harnesses and asks
# before touching any config). Safe to re-run: it updates the existing copy
# in place instead of re-cloning.
set -euo pipefail

REPO_URL="https://github.com/Deetss/omniline.git"
ARCHIVE_URL_BASE="https://github.com/Deetss/omniline/archive/refs/heads"
REF="main"
INSTALL_DIR="${OMNILINE_HOME:-$HOME/.local/share/omniline}"

usage() {
  cat <<'EOF'
omniline installer

Usage: install.sh [--dir <path>] [--ref <branch>]

  --dir <path>   where to install omniline (default: ~/.local/share/omniline,
                 or $OMNILINE_HOME if set)
  --ref <ref>    branch to install (default: main)
  -h, --help     show this help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "omniline: unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

log() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 is required but wasn't found on PATH."

py_ok=$(python3 - <<'PYEOF'
import sys
print("1" if sys.version_info >= (3, 8) else "0")
PYEOF
)
[ "$py_ok" = "1" ] || die "python3 >= 3.8 is required (found: $(python3 --version 2>&1))."

if command -v git >/dev/null 2>&1; then
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "updating existing install at $INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch --depth 1 origin "$REF"
    git -C "$INSTALL_DIR" checkout -q FETCH_HEAD
  else
    log "cloning omniline ($REF) into $INSTALL_DIR"
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$INSTALL_DIR"
  fi
else
  command -v curl >/dev/null 2>&1 || die "need either git or curl to fetch omniline."
  command -v tar >/dev/null 2>&1 || die "need tar to unpack the downloaded archive."
  log "git not found -- downloading a source archive instead"
  tmp_tar="$(mktemp)"
  trap 'rm -f "$tmp_tar"' EXIT
  curl -fsSL "$ARCHIVE_URL_BASE/$REF.tar.gz" -o "$tmp_tar" \
    || die "could not download $ARCHIVE_URL_BASE/$REF.tar.gz"
  rm -rf "$INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"
  tar -xzf "$tmp_tar" -C "$INSTALL_DIR" --strip-components=1
fi

log "installed to $INSTALL_DIR"

# bin/install prompts interactively (which harness? overwrite existing
# config?). When this script itself arrived via `curl | bash`, stdin is the
# pipe carrying the script, not the terminal -- reattach it so those prompts
# actually work instead of reading EOF.
if [ -t 1 ] && [ -r /dev/tty ]; then
  exec < /dev/tty
fi

cd "$INSTALL_DIR"
exec python3 bin/install
