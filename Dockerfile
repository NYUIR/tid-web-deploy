# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Missile TID Web Deployment
# Multi-stage build: base deps → TID library → Flask web layer
# ─────────────────────────────────────────────────────────────────────────────
FROM ubuntu:20.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System-level dependencies (from Middlebury README)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ \
        libcurl4-openssl-dev \
        libgeos-dev \
        python3 python3-pip python3-dev \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Alias python → python3
RUN ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

# ── Stage: Install TID library and its requirements ─────────────────────────
# Copy the full Middlebury TID repo into the container.
# Users should place the cloned missile-tid repo alongside this Dockerfile
# or adjust the COPY path accordingly.
COPY missile-tid/ /app/missile-tid/

# Install the original Middlebury requirements
RUN pip install --no-cache-dir -r /app/missile-tid/requirements.txt \
    && pip install --no-cache-dir -e /app/missile-tid/

# Copy the example config to the live config location
RUN cp /app/missile-tid/config/configuration.yml.example \
       /app/missile-tid/config/configuration.yml

# ── Stage: Install web layer ────────────────────────────────────────────────
COPY requirements-web.txt /app/
RUN pip install --no-cache-dir -r /app/requirements-web.txt

COPY app.py          /app/
COPY templates/      /app/templates/

# Create working directories
RUN mkdir -p /app/output /app/logs

# Expose the default Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Run via gunicorn in production
CMD ["python", "-m", "gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "600", \
     "app:app"]
