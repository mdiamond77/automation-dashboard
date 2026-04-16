"""
server.py — Mathnasium Automation Dashboard
Always-on local web server on port 8080.
"""

import json
import os
import socket
import subprocess
import time

from flask import Flask, Response, redirect, render_template, stream_with_context

app = Flask(__name__)

PYTHON = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"

# ── Runnable scripts (output streamed live in browser) ────────────────────────
SCRIPTS = {
    "radius-cc-lists": {
        "name": "Radius → CC Contact Lists",
        "description": "Downloads the 3 Guardian reports from Radius and uploads them as dated contact lists in Constant Contact.",
        "command": [PYTHON, "main.py"],
        "cwd": "/Users/mattdiamond/radius-cc-lists",
        "icon": "📋",
        "category": "Mathnasium",
    },
    "appointy-export": {
        "name": "Appointy Export",
        "description": "Exports appointment data from Appointy. Normally runs automatically each night via GitHub Actions.",
        "command": [PYTHON, "scripts/appointy_export.py"],
        "cwd": "/Users/mattdiamond/Mathnasium_automation",
        "icon": "📤",
        "category": "Mathnasium",
    },
    "fantasy-report": {
        "name": "Fantasy Baseball Report",
        "description": "Generates today's fantasy baseball matchup report and saves it as a PDF.",
        "command": [PYTHON, "run_report.py", "--force", "--no-print"],
        "cwd": "/Users/mattdiamond/fantasy_baseball",
        "icon": "⚾",
        "category": "Fantasy Baseball",
    },
}

# ── Web apps (launch server if needed, then open in browser) ──────────────────
WEB_APPS = [
    {
        "id": "fantasy-advisor",
        "name": "Fantasy Advisor",
        "description": "Daily lineup recommendations and player analysis for your Yahoo Fantasy leagues.",
        "url": "https://fantasy-advisor.onrender.com/",
        "port": None,
        "command": None,
        "cwd": None,
        "icon": "🏆",
        "category": "Fantasy Baseball",
    },
    {
        "id": "fantasy-scheduler",
        "name": "Fantasy Scheduler",
        "description": "Schedule when fantasy baseball reports are automatically generated and printed.",
        "url": "http://localhost:8765",
        "port": 8765,
        "command": [PYTHON, "scheduler_server.py"],
        "cwd": "/Users/mattdiamond/fantasy_baseball",
        "icon": "📅",
        "category": "Fantasy Baseball",
    },
]

# ── Interactive scripts (require terminal input — open in Terminal) ────────────
INTERACTIVE = [
    {
        "id": "cc-newsletter",
        "name": "CC Newsletter Update",
        "description": "Updates the monthly Constant Contact newsletter. Edit your content in CC first, then run this.",
        "command": f"cd ~/cc-newsletter-automation && {PYTHON} main.py",
        "icon": "📧",
        "category": "Mathnasium",
    },
]


@app.route("/")
def index():
    return render_template(
        "index.html",
        scripts=SCRIPTS,
        web_apps=WEB_APPS,
        interactive=INTERACTIVE,
    )


@app.route("/run/<script_id>")
def run_script(script_id):
    if script_id not in SCRIPTS:
        return "Script not found", 404

    script = SCRIPTS[script_id]

    def generate():
        try:
            process = subprocess.Popen(
                script["command"],
                cwd=script["cwd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            for line in process.stdout:
                yield f"data: {json.dumps(line.rstrip())}\n\n"
            process.wait()
            code = process.returncode
            status = "__DONE__" if code == 0 else f"__ERROR__ (exit code {code})"
            yield f"data: {json.dumps(status)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps(f'Error: {e}')}\n\n"
            yield f"data: {json.dumps('__ERROR__')}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _port_open(port):
    """Return True if something is already listening on the port."""
    try:
        with socket.create_connection(("localhost", port), timeout=1):
            return True
    except OSError:
        return False


@app.route("/launch/<app_id>")
def launch_app(app_id):
    """Start a web app server if not already running, then redirect to it."""
    app_cfg = next((a for a in WEB_APPS if a["id"] == app_id), None)
    if not app_cfg:
        return "Not found", 404

    # External apps (no local server to start) — redirect straight there
    if not app_cfg.get("port"):
        return redirect(app_cfg["url"])

    if not _port_open(app_cfg["port"]):
        subprocess.Popen(
            app_cfg["command"],
            cwd=app_cfg["cwd"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait up to 5 seconds for the server to start
        for _ in range(10):
            time.sleep(0.5)
            if _port_open(app_cfg["port"]):
                break

    return redirect(app_cfg["url"])


@app.route("/open-terminal/<script_id>")
def open_terminal(script_id):
    script = next((s for s in INTERACTIVE if s["id"] == script_id), None)
    if not script:
        return "Not found", 404
    cmd = script["command"]
    apple = f'tell application "Terminal" to do script "{cmd}"'
    subprocess.Popen(["osascript", "-e", apple])
    return ("", 204)


if __name__ == "__main__":
    app.run(port=8080, debug=False)
