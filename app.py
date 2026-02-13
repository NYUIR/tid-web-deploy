"""
TID Web Application
Flask-based web interface for the Middlebury Missile TID detection tool.
Wraps the existing command-line demos into a browser-accessible dashboard.
"""

import os
import json
import glob
import logging
import threading
import subprocess
import uuid
import shutil
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, jsonify, request,
    send_from_directory
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
# Locate demo scripts dynamically
# ---------------------------------------------------------------------------
def find_file(name, search_root="missile-tid"):
    for root, dirs, files in os.walk(search_root):
        if name in files:
            return os.path.join(root, name)
    return None

def find_any_file(names, search_root="missile-tid"):
    for name in names:
        result = find_file(name, search_root)
        if result:
            return result
    return None

def find_all_files(search_root="missile-tid"):
    py_files = []
    for root, dirs, files in os.walk(search_root):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return py_files

logger.info("=== All .py files in missile-tid ===")
for f in find_all_files():
    logger.info("  %s", f)
logger.info("=== end ===")

VANDENBERG_SCRIPT = find_any_file([
    "vandenberg.py",
    "vandenburg.py",
    "Vandenberg.py",
    "Vandenburg.py",
])

LIVE_SCRIPT = find_any_file([
    "live.py",
    "Live.py",
])

MISSILE_TID_ROOT = None
req_file = find_file("requirements.txt", "missile-tid")
if req_file:
    MISSILE_TID_ROOT = os.path.dirname(req_file)

logger.info("Vandenberg script: %s", VANDENBERG_SCRIPT)
logger.info("Live script: %s", LIVE_SCRIPT)
logger.info("Missile-TID root: %s", MISSILE_TID_ROOT)

# ---------------------------------------------------------------------------
# In-memory job tracker
# ---------------------------------------------------------------------------
jobs = {}


def _run_demo(job_id, demo_script, extra_args=None):
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

    cwd = MISSILE_TID_ROOT or os.path.dirname(demo_script) or "."
    abs_script = os.path.abspath(demo_script)

    cmd = ["python", abs_script] + (extra_args or [])
    logger.info("Starting job %s: %s (cwd=%s)", job_id, " ".join(cmd), cwd)

    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(exist_ok=True)
    abs_output_dir = str(job_output_dir.resolve())

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("JOB_TIMEOUT", 600)),
            cwd=cwd,
            env={
                **os.environ,
                "TID_OUTPUT_DIR": abs_output_dir,
                "PYTHONPATH": cwd + ":" + os.environ.get("PYTHONPATH", ""),
            },
        )
        jobs[job_id]["stdout"] = result.stdout[-5000:]
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

    # Search broadly for generated output files
    artifacts = []
    for ext in ("*.png", "*.gif", "*.mp4", "*.html", "*.jpg", "*.svg"):
        artifacts.extend(
            str(p.relative_to(OUTPUT_DIR)) for p in job_output_dir.rglob(ext)
        )
    # Also check if the script saved files in the cwd
    for ext in ("*.png", "*.gif", "*.mp4", "*.jpg", "*.svg"):
        for p in Path(cwd).glob(ext):
            dest = job_output_dir / p.name
            if not dest.exists():
                try:
                    shutil.copy2(str(p), str(dest))
                    artifacts.append(str(dest.relative_to(OUTPUT_DIR)))
                except Exception:
                    pass

    jobs[job_id]["artifacts"] = artifacts
    logger.info(
        "Job %s finished: %s (%d artifacts)",
        job_id, jobs[job_id]["status"], len(artifacts)
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/demos", methods=["GET"])
def list_demos():
    demos = [
        {
            "id": "vandenberg",
            "name": "Vandenberg Falcon 9 Detection",
            "description": (
                "Replay detection of a Falcon 9 launch from Vandenberg SFB, CA "
                "on 12 June 2019. Produces an animation of the traveling "
                "ionospheric disturbance."
            ),
            "script": VANDENBERG_SCRIPT or "NOT FOUND",
            "available": VANDENBERG_SCRIPT is not None,
            "type": "replay",
        },
        {
            "id": "korea",
            "name": "Korean Peninsula Live Monitor",
            "description": (
                "Monitors GNSS data near the Korean peninsula for potential "
                "ballistic missile launches in near-real-time."
            ),
            "script": LIVE_SCRIPT or "NOT FOUND",
            "available": LIVE_SCRIPT is not None,
            "type": "live",
        },
    ]
    return jsonify(demos)


@app.route("/api/run", methods=["POST"])
def run_demo():
    body = request.get_json(force=True)
    demo_id = body.get("demo_id")
    if demo_id not in ("vandenberg", "korea"):
        return jsonify({"error": "Unknown demo_id"}), 400

    script = VANDENBERG_SCRIPT if demo_id == "vandenberg" else LIVE_SCRIPT
    if not script:
        return jsonify({
            "error": "Demo script not found in missile-tid directory.",
            "job_id": "error",
            "status": "failed"
        }), 500

    job_id = str(uuid.uuid4())[:8]
    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(exist_ok=True)
    abs_output_dir = str(job_output_dir.resolve())

    # Each demo script has different argument formats:
    # vandenberg.py uses: -o OUTPUT_PATH [-v]
    # live.py uses: output_folder [hours_to_run]
    if demo_id == "vandenberg":
        extra_args = ["-o", abs_output_dir]
    else:
        extra_args = [abs_output_dir, "1"]

    jobs[job_id] = {
        "job_id": job_id,
        "demo_id": demo_id,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "stdout": "",
        "stderr": "",
        "artifacts": [],
    }

    thread = threading.Thread(target=_run_demo, args=(job_id, script, extra_args), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id, "status": "queued"}), 202


@app.route("/api/jobs", methods=["GET"])
def list_jobs():
    ordered = sorted(jobs.values(), key=lambda j: j["created_at"], reverse=True)
    return jsonify(ordered)


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/artifacts/<path:filepath>")
def serve_artifact(filepath):
    return send_from_directory(OUTPUT_DIR, filepath)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "vandenberg_script": VANDENBERG_SCRIPT,
        "live_script": LIVE_SCRIPT,
        "missile_tid_root": MISSILE_TID_ROOT,
        "all_py_files": find_all_files(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
