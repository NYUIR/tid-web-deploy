#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# entrypoint.sh
#
# Runtime entrypoint for the Docker container.
# Sets up NASA Earthdata credentials from environment variables
# (needed because Render injects env vars at runtime, not build time)
# then launches the Flask app.
# ─────────────────────────────────────────────────────────────────
set -e

# ── Set up .netrc for CDDIS authentication ──
if [ -n "$EARTHDATA_USER" ] && [ -n "$EARTHDATA_PASS" ]; then
    cat > ~/.netrc <<EOF
machine urs.earthdata.nasa.gov
login $EARTHDATA_USER
password $EARTHDATA_PASS
EOF
    chmod 600 ~/.netrc
    echo "[entrypoint] NASA Earthdata credentials configured"
else
    echo "[entrypoint] WARNING: EARTHDATA_USER / EARTHDATA_PASS not set"
    echo "[entrypoint]          International (non-US) station downloads will fail"
    echo "[entrypoint]          US CORS stations (Vandenberg demo) will still work"
fi

# ── Launch the app ──
exec "$@"
