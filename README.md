# Missile TID — Web Deployment

A browser-based deployment wrapper for the [Middlebury Missile TID](https://github.com/middlebury) library, developed for NYU International Relations. This package replaces the command-line demo workflow with a Flask web application served through Docker, so researchers can launch TID detection runs from any browser without touching a terminal.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Browser (any device)                                │
│  ┌────────────────────────────────┐                  │
│  │  Dashboard UI  (index.html)    │                  │
│  │  • Select demo scenario        │                  │
│  │  • View animations / artifacts │                  │
│  │  • Read console output         │                  │
│  └────────────┬───────────────────┘                  │
│               │ HTTP / JSON                          │
├───────────────┼──────────────────────────────────────┤
│  Flask App    │  (app.py)                            │
│  ┌────────────▼───────────────────┐                  │
│  │  /api/run   → spawn subprocess │                  │
│  │  /api/jobs  → job status       │                  │
│  │  /api/artifacts → images/video │                  │
│  └────────────┬───────────────────┘                  │
│               │ subprocess                           │
│  ┌────────────▼───────────────────┐                  │
│  │  Middlebury missile-tid        │                  │
│  │  demos/vandenburg.py           │                  │
│  │  demos/live.py                 │                  │
│  └────────────────────────────────┘                  │
│                                                      │
│  Docker container (Ubuntu 20.04)                     │
└──────────────────────────────────────────────────────┘
```

## Prerequisites

- **Docker** (v20+) and **Docker Compose** (v2+)
- A clone of the Middlebury `missile-tid` repository

That's it — all Python dependencies, system libraries, and configuration are handled inside the container.

---

## Quick Start

### 1. Clone both repositories

```bash
# Clone this web deployment wrapper
git clone <this-repo-url> tid-web-deploy
cd tid-web-deploy

# Clone the Middlebury TID repo into a subdirectory
git clone <middlebury-missile-tid-url> missile-tid
```

### 2. Build and run

```bash
docker compose up --build
```

### 3. Open the dashboard

Navigate to **http://localhost:5000** in any browser.

From the dashboard you can:

1. **Select** either the Vandenberg replay demo or the Korean peninsula live monitor.
2. **Click "Run Detection"** to launch the analysis.
3. **Watch progress** in the console tab; generated animations and images appear in the artifacts tab once the job finishes.

---

## File Layout

```
tid-web-deploy/
├── app.py                 # Flask application (API + page routes)
├── Dockerfile             # Container build recipe
├── docker-compose.yml     # One-command deployment
├── requirements-web.txt   # Flask / gunicorn dependencies
├── templates/
│   └── index.html         # Dashboard frontend
├── static/                # (optional) extra CSS / JS / images
├── missile-tid/           # ← place the Middlebury repo here
│   ├── demos/
│   ├── config/
│   ├── requirements.txt
│   └── ...
└── README.md              # This file
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Port the web server binds to |
| `FLASK_DEBUG` | `0` | Set to `1` for live reload during development |
| `SECRET_KEY` | `change-me-in-production` | Flask session key |
| `JOB_TIMEOUT` | `600` | Max seconds a demo job may run before being killed |

Override via a `.env` file in the project root or inline:

```bash
PORT=8080 docker compose up --build
```

---

## Running Without Docker (development)

If you prefer running directly on your host machine:

```bash
# 1. Install system deps (Ubuntu)
sudo apt install gcc g++ libcurl4-openssl-dev libgeos-dev

# 2. Install Python packages
python -m pip install -r missile-tid/requirements.txt
python -m pip install -e ./missile-tid/
python -m pip install -r requirements-web.txt

# 3. Copy config
cp missile-tid/config/configuration.yml.example missile-tid/config/configuration.yml

# 4. Run
python app.py
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serve the dashboard UI |
| `GET` | `/api/demos` | List available demo scenarios |
| `POST` | `/api/run` | Start a demo job (`{"demo_id": "vandenberg"}`) |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/<id>` | Get status + artifacts for a job |
| `GET` | `/api/artifacts/<path>` | Serve a generated file (image, video, etc.) |
| `GET` | `/api/health` | Health check endpoint |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pycurl` / `libffi` version mismatch | The Docker build installs `libcurl4-openssl-dev` which should resolve this. If running locally, reinstall `pycurl` without a version pin. |
| `free(): invalid size` on animation | Rebuild Shapely from source: `pip install --force-reinstall shapely --no-binary shapely`. May require `Cython` first. |
| `OSError: Could not find lib geos_c` | Ensure `libgeos-dev` is installed (Docker handles this) or, on macOS, run `brew install geos`. |
| Job stays in "running" forever | Check `logs/app.log` inside the container. The default timeout is 600 s; increase via `JOB_TIMEOUT`. |

---

## License

This deployment wrapper is provided for academic use by NYU International Relations. The underlying Missile TID library is subject to the Middlebury project's own license and contribution guidelines.
