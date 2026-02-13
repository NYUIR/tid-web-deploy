FROM ubuntu:20.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System-level dependencies (from Middlebury README)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ \
        libcurl4-openssl-dev \
        libssl-dev \
        libgeos-dev \
        python3 python3-pip python3-dev \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Copy the Middlebury TID repo
COPY missile-tid/ /app/missile-tid/

# Install pycurl separately with the correct SSL backend
RUN pip install --no-cache-dir pycurl --global-option="--with-openssl"

# Install remaining requirements (skip pycurl since it's already installed)
RUN sed '/pycurl/d' /app/missile-tid/requirements.txt > /tmp/requirements-filtered.txt \
    && pip install --no-cache-dir -r /tmp/requirements-filtered.txt \
    && pip install --no-cache-dir -e /app/missile-tid/

# Copy the example config
RUN cp /app/missile-tid/config/configuration.yml.example \
       /app/missile-tid/config/configuration.yml

# Install web layer
COPY requirements-web.txt /app/
RUN pip install --no-cache-dir -r /app/requirements-web.txt

COPY app.py          /app/
COPY templates/      /app/templates/

RUN mkdir -p /app/output /app/logs

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

CMD ["python", "-m", "gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "600", \
     "app:app"]
