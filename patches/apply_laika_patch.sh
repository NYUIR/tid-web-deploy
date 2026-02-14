#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# patches/apply_laika_patch.sh
#
# Patches the installed laika library to download GNSS station
# observation data from NASA CDDIS (international IGS stations)
# in addition to the default US CORS servers.
#
# Called from Dockerfile after laika is installed via pip.
# ─────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 1. Find where laika is installed ──
LAIKA_DIR=$(python3 -c "import laika, os; print(os.path.dirname(laika.__file__))" 2>/dev/null || true)

if [ -z "$LAIKA_DIR" ] || [ ! -d "$LAIKA_DIR" ]; then
    echo "WARNING: laika package not found. Patch skipped."
    echo "         (This is OK if laika installs later or is not needed.)"
    exit 0
fi

echo "Found laika at: $LAIKA_DIR"

# ── 2. Back up original and install patched downloader.py ──
if [ -f "$LAIKA_DIR/downloader.py" ]; then
    cp "$LAIKA_DIR/downloader.py" "$LAIKA_DIR/downloader.py.orig"
    echo "Backed up original downloader.py"
fi

cp "$SCRIPT_DIR/downloader.py" "$LAIKA_DIR/downloader.py"
echo "Installed patched downloader.py → CDDIS fallback enabled"
