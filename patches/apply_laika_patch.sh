#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# patches/apply_laika_patch.sh
#
# Surgically patches the INSTALLED laika downloader.py to add:
#   1. CDDIS_OBS_BASE_URL constant
#   2. .netrc authentication in https_download_file()
#   3. CDDIS fallback in download_cors_station()
#
# Does NOT replace the file — preserves all existing functions
# (including download_orbits_russia_src, etc.)
# ─────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Find where laika is installed ──
LAIKA_DIR=$(python3 -c "import laika, os; print(os.path.dirname(laika.__file__))" 2>/dev/null || true)

if [ -z "$LAIKA_DIR" ] || [ ! -d "$LAIKA_DIR" ]; then
    echo "WARNING: laika package not found. Patch skipped."
    exit 0
fi

TARGET="$LAIKA_DIR/downloader.py"
echo "Found laika at: $LAIKA_DIR"
echo "Patching: $TARGET"

# Back up original
cp "$TARGET" "$TARGET.orig"

# Run the surgical Python patcher
python3 "$SCRIPT_DIR/patch_downloader.py" "$TARGET"

echo "Laika CDDIS patch applied successfully."
