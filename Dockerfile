# ─────────────────────────────────────────────────────────────
# Missile TID — Web Deployment
# Docker build recipe (Ubuntu 20.04 + Python 3.10)
#
# Includes:
#   • Middlebury missile-tid library + all scientific deps
#   • Flask web application
#   • Laika CDDIS patch for international IGS station support
#   • NASA Earthdata credential setup at runtime
# ─────────────────────────────────────────────────────────────
FROM python:3.10-slim-bullseye

# ── System dependencies ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ gfortran \
    libcurl4-openssl-dev libssl-dev \
    libgeos-dev libgeos++-dev \
    libffi-dev \
    git curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Copy everything into the image ──
COPY . /app

# ── Install missile-tid requirements ──
# The missile-tid directory may contain a nested folder from GitHub ZIP download
# Handle both flat and nested layouts
RUN if [ -f missile-tid/requirements.txt ]; then \
        pip install --no-cache-dir -r missile-tid/requirements.txt; \
    elif ls missile-tid/*/requirements.txt 2>/dev/null; then \
        NESTED=$(ls missile-tid/*/requirements.txt | head -1) && \
        NESTED_DIR=$(dirname "$NESTED") && \
        mv "$NESTED_DIR"/* missile-tid/ 2>/dev/null || true && \
        pip install --no-cache-dir -r missile-tid/requirements.txt; \
    fi

# ── Install missile-tid as editable package ──
RUN if [ -f missile-tid/pyproject.toml ] || [ -f missile-tid/setup.py ]; then \
        pip install --no-cache-dir -e ./missile-tid/; \
    fi

# ── Copy configuration file ──
RUN if [ -f missile-tid/config/configuration.yml.example ] && \
       [ ! -f missile-tid/config/configuration.yml ]; then \
        cp missile-tid/config/configuration.yml.example missile-tid/config/configuration.yml; \
    fi

# ── Install Flask web dependencies ──
RUN pip install --no-cache-dir -r requirements-web.txt

# ── Apply the laika CDDIS patch ──
# This patches laika's downloader.py to add NASA CDDIS as a fallback
# source for international IGS station RINEX data, and enables .netrc
# authentication in pycurl for NASA Earthdata OAuth.
RUN chmod +x patches/apply_laika_patch.sh && \
    bash patches/apply_laika_patch.sh

# ── Copy the Kapustin Yar demo into missile-tid/demos/ ──
RUN if [ -d missile-tid/demos ]; then \
        cp kapustin_yar.py missile-tid/demos/kapustin_yar.py; \
    fi

# ── Copy one-shot live.py into missile-tid/demos/ ──
RUN if [ -d missile-tid/demos ] && [ -f live.py ]; then \
        cp live.py missile-tid/demos/live.py; \
    fi

# ── Runtime entrypoint (sets up .netrc from env vars) ──
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ── Create required directories ──
RUN mkdir -p logs output static

EXPOSE 5000

# Entrypoint handles .netrc credential setup at runtime,
# then exec's the CMD below
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "app.py"]
