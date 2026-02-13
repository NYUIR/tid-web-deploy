"""
TID Web Application
Flask-based web interface for the Middlebury Missile TID detection tool.
Wraps the existing command-line demos into a browser-accessible dashboard.
"""

import os
import io
import json
import glob
import base64
import logging
import threading
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Flask, render_template, jsonify, request,
    send_from_directory, Response
)

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "tid-dev-key")

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory job tracker  (swap for Redis/DB in production)
# ---------------------------------------------------------------------------
jobs = {}


def _run_demo(job_id, demo_script, extra_args=None):
    """Execute a TID demo script in a subprocess and capture output."""
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

    cmd = ["python", demo_script] + (extra_args or [])
    logger.info("Starting job %s: %s", job_id, " ".join(cmd))

    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(exist_ok=True)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("JOB_TIMEOUT", 600)),
            env={**os.environ, "TID_OUTPUT_DIR": str(job_output_dir)},
        )
        jobs[job_id]["stdout"] = result.stdout[-5000:]  # keep tail
        jobs[job_id]["stderr"] = result.stderr[-5000:]
        jobs[job_id]["returncode"] = result.returncode
        jobs[job_id]["status"] = "completed" if result.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        jobs[job_id]["status"] = "timeout"
        jobs[job_id]["stderr"] = "Job exceeded maximum allowed runtime."
    except Exception as exc:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["stderr"] = str(exc)
    finally:
        jobs[job_id]["finished_at"] = datetime.utcnow().isoformat()

    # Collect any generated images / animations
    artifacts = []
    for ext in ("*.png", "*.gif", "*.mp4", "*.html"):
        artifacts.extend(
            str(p.relative_to(OUTPUT_DIR)) for p in job_output_dir.glob(ext)
        )
    jobs[job_id]["artifacts"] = artifacts
    logger.info("Job %s finished: %s (%d artifacts)", job_id, jobs[job_id]["status"], len(artifacts))


# ---------------------------------------------------------------------------
# Routes – pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes – API
# ---------------------------------------------------------------------------
@app.route("/api/demos", methods=["GET"])
def list_demos():
    """Return available demo configurations."""
    demos = [
        {
            "id": "vandenberg",
            "name": "Vandenberg Falcon 9 Detection",
            "description": (
                "Replay detection of a Falcon 9 launch from Vandenberg SFB, CA "
                "on 12 June 2019.  Produces an animation of the traveling "
                "ionospheric disturbance."
            ),
            "script": "missile-tid/demos/vandenburg.py",
            "type": "replay",
        },
        {
            "id": "korea",
            "name": "Korean Peninsula Live Monitor",
            "description": (
                "Monitors GNSS data near the Korean peninsula for potential "
                "ballistic missile launches in near-real-time."
            ),
            "script": "missile-tid/demos/live.py",
            "type": "live",
        },
    ]
    return jsonify(demos)


@app.route("/api/run", methods=["POST"])
def run_demo():
    """Start a demo job asynchronously."""
    body = request.get_json(force=True)
    demo_id = body.get("demo_id")
    if demo_id not in ("vandenberg", "korea"):
        return jsonify({"error": "Unknown demo_id"}), 400

    script = "missile-tid/demos/vandenburg.py" if demo_id == "vandenberg" else "missile-tid/demos/live.py"
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "job_id": job_id,
        "demo_id": demo_id,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "stdout": "",
        "stderr": "",
        "artifacts": [],
    }

    thread = threading.Thread(target=_run_demo, args=(job_id, script), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id, "status": "queued"}), 202


@app.route("/api/jobs", methods=["GET"])
def list_jobs():
    """List all jobs (most recent first)."""
    ordered = sorted(jobs.values(), key=lambda j: j["created_at"], reverse=True)
    return jsonify(ordered)


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    """Return details of a single job."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/artifacts/<path:filepath>")
def serve_artifact(filepath):
    """Serve a generated artifact (image, animation, etc.)."""
    return send_from_directory(OUTPUT_DIR, filepath)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
