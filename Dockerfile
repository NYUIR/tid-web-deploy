FROM ubuntu:22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System-level dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ \
        libcurl4-openssl-dev \
        libssl-dev \
        libgeos-dev \
        libgeos++-dev \
        libproj-dev \
        proj-data \
        python3 python3-pip python3-dev \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Copy the Middlebury TID repo
COPY missile-tid/ /app/missile-tid-raw/

# Flatten: if there is a single nested subfolder, move its contents up
RUN if [ $(ls -d /app/missile-tid-raw/*/ 2>/dev/null | wc -l) -eq 1 ] && \
       [ ! -f /app/missile-tid-raw/requirements.txt ]; then \
        mv /app/missile-tid-raw/*/* /app/missile-tid-raw/ 2>/dev/null; \
        mv /app/missile-tid-raw/*/.[!.]* /app/missile-tid-raw/ 2>/dev/null; \
    fi && \
    mv /app/missile-tid-raw /app/missile-tid

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install pycurl separately with the correct SSL backend
RUN pip install --no-cache-dir pycurl --global-option="--with-openssl"

# Install compatible versions of Shapely and Cartopy for Ubuntu 22.04 GEOS
RUN pip install --no-cache-dir "Shapely>=2.0,<3.0"
RUN pip install --no-cache-dir "Cartopy>=0.21"

# Install remaining requirements (skip pycurl, Shapely, Cartopy)
RUN sed '/pycurl/d; /Shapely/d; /shapely/d; /Cartopy/d; /cartopy/d' \
        /app/missile-tid/requirements.txt > /tmp/requirements-filtered.txt \
    && pip install --no-cache-dir -r /tmp/requirements-filtered.txt

# Make missile-tid importable via PYTHONPATH
ENV PYTHONPATH="/app/missile-tid:${PYTHONPATH}"

# Force matplotlib to use non-interactive backend
ENV MPLBACKEND=agg

# Copy the example config if it exists
RUN if [ -f /app/missile-tid/config/configuration.yml.example ]; then \
        cp /app/missile-tid/config/configuration.yml.example \
           /app/missile-tid/config/configuration.yml; \
    fi

# Install web layer
COPY requirements-web.txt /app/
RUN pip install --no-cache-dir -r /app/requirements-web.txt

COPY app.py          /app/
COPY templates/      /app/templates/
COPY entrypoint.sh   /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN mkdir -p /app/output /app/logs

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "app.py"]
