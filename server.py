"""
server.py — Mathnasium Automation Dashboard
Always-on local web server on port 8080.
"""

import json
import os
import re
import socket
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime as _dt, timezone, timedelta

from flask import Flask, Response, redirect, render_template, request, jsonify, stream_with_context

PROJECTS_FILE = os.environ.get("PROJECTS_FILE", os.path.join(os.path.dirname(__file__), "future_projects.json"))

def _get_gh_token() -> str | None:
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or None
    except Exception:
        return None

_GH_TOKEN = _get_gh_token()

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
    "cc-newsletter": {
        "name": "CC Newsletter Update",
        "description": "Updates the monthly Constant Contact newsletter. Edit your content in CC first, then run this.",
        "command": [PYTHON, "main.py"],
        "cwd": "/Users/mattdiamond/cc-newsletter-automation",
        "icon": "📧",
        "category": "Mathnasium",
        "confirm": "Have you finished editing the content in Constant Contact?",
        "before": ["radius-cc-lists"],
    },

}

SCRIPTS["page-goals"] = {
    "name": "Student Page Goals",
    "description": "Calculates monthly page goals for each student from Radius data.",
    "command": [PYTHON, "main.py", "--trigger", "manual"],
    "cwd": "/Users/mattdiamond/mathnasium-page-goals",
    "icon": "📊",
    "category": "Mathnasium",
    "hidden": True,
}

SCRIPTS["birthdays-levelups"] = {
    "name": "Birthdays & Level Ups",
    "description": "Emails each center director a monthly list of student birthdays and level-ups.",
    "command": [PYTHON, "main.py"],
    "cwd": "/Users/mattdiamond/mathnasium-birthdays-levelups",
    "icon": "🎂",
    "category": "Mathnasium",
    "hidden": True,
}

SCRIPTS["hold-reminders"] = {
    "name": "Hold Reminder Emails",
    "description": "Emails each center director a list of students coming off hold this month.",
    "command": [PYTHON, "main.py", "--trigger", "manual"],
    "cwd": "/Users/mattdiamond/mathnasium-hold-reminders",
    "icon": "⏸️",
    "category": "Mathnasium",
    "hidden": True,
}

SCRIPTS["binder-audit"] = {
    "name": "Binder Audit",
    "description": "Flags students overdue for a Progress Check or Assessment and emails per-center reports.",
    "command": [PYTHON, "main.py", "--trigger", "manual"],
    "cwd": "/Users/mattdiamond/mathnasium-binder-audit",
    "icon": "📋",
    "category": "Mathnasium",
    "hidden": True,
}

SCRIPTS["attendance-alerts"] = {
    "name": "Attendance Alerts",
    "description": "Weekly Monday email: students attending < 75% of allowed sessions.",
    "command": [PYTHON, "main.py", "--trigger", "manual"],
    "cwd": "/Users/mattdiamond/mathnasium-attendance-alerts",
    "icon": "📅",
    "category": "Mathnasium",
    "hidden": True,
}

# ── Reports registry (shown on /reports page) ─────────────────────────────────
REPORTS = [
    {
        "id": "radius-cc-lists",
        "name": "Radius → CC Contact Lists",
        "schedule": "Monthly",
        "script_id": "radius-cc-lists",
        "run_log_path": None,
    },
    {
        "id": "cc-newsletter",
        "name": "CC Newsletter Update",
        "schedule": "Monthly",
        "script_id": "cc-newsletter",
        "run_log_path": None,
    },
    {
        "id": "student-page-goals",
        "name": "Student Page Goals",
        "schedule": "1st of month",
        "script_id": "page-goals",
        "run_log_path": "/Users/mattdiamond/mathnasium-page-goals/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-page-goals/main/run_log.json",
    },
    {
        "id": "birthdays-levelups",
        "name": "Birthdays & Level Ups",
        "schedule": "1st of month",
        "script_id": "birthdays-levelups",
        "run_log_path": "/Users/mattdiamond/mathnasium-birthdays-levelups/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-birthdays-levelups/main/run_log.json",
    },
    {
        "id": "hold-reminders",
        "name": "Hold Reminder Emails",
        "schedule": "Last Mon/Tue/Thu of month",
        "script_id": "hold-reminders",
        "run_log_path": "/Users/mattdiamond/mathnasium-hold-reminders/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-hold-reminders/main/run_log.json",
    },
    {
        "id": "binder-audit",
        "name": "Binder Audit",
        "schedule": "15th of month",
        "script_id": "binder-audit",
        "run_log_path": "/Users/mattdiamond/mathnasium-binder-audit/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-binder-audit/main/run_log.json",
    },
    {
        "id": "attendance-alerts",
        "name": "Attendance Alerts",
        "schedule": "Weekly (Monday)",
        "script_id": "attendance-alerts",
        "run_log_path": "/Users/mattdiamond/mathnasium-attendance-alerts/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-attendance-alerts/main/run_log.json",
    },
]

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

INTERACTIVE = []


@app.route("/reports")
def reports_redirect():
    return redirect("/")


@app.route("/personal")
def personal_page():
    return render_template("personal.html", web_apps=WEB_APPS)


@app.route("/")
def index():
    report_rows = []
    for report in REPORTS:
        path = report.get("run_log_path")
        url  = report.get("run_log_url")
        log = _load_run_log(path, url) if (path or url) else []
        auto_runs   = [r for r in log if r.get("trigger") == "auto"]
        manual_runs = [r for r in log if r.get("trigger") == "manual"]
        script = SCRIPTS.get(report["script_id"], {})
        report_rows.append({
            **report,
            "icon":        script.get("icon", "📄"),
            "description": script.get("description", ""),
            "confirm":     script.get("confirm"),
            "last_auto":   _fmt_run(auto_runs[-1]   if auto_runs   else None),
            "last_manual": _fmt_run(manual_runs[-1] if manual_runs else None),
        })
    return render_template("index.html", reports=report_rows)


@app.route("/run/<script_id>")
def run_script(script_id):
    if script_id not in SCRIPTS:
        return "Script not found", 404

    script = SCRIPTS[script_id]
    sequence = [
        SCRIPTS[sid] for sid in script.get("before", []) if sid in SCRIPTS
    ] + [script]

    def generate():
        for idx, s in enumerate(sequence):
            if idx > 0:
                yield f"data: {json.dumps('─' * 40)}\n\n"
            if len(sequence) > 1:
                yield f"data: {json.dumps('▶ ' + s['name'])}\n\n"
            try:
                process = subprocess.Popen(
                    s["command"],
                    cwd=s["cwd"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
                for line in process.stdout:
                    yield f"data: {json.dumps(line.rstrip())}\n\n"
                process.wait()
                if process.returncode != 0:
                    yield f"data: {json.dumps(f'__ERROR__ (exit code {process.returncode})')}\n\n"
                    return
            except Exception as e:
                yield f"data: {json.dumps(f'Error: {e}')}\n\n"
                yield f"data: {json.dumps('__ERROR__')}\n\n"
                return
        yield f"data: {json.dumps('__DONE__')}\n\n"

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


def _load_run_log(path: str, url: str = None) -> list[dict]:
    """Load run log, preferring GitHub (always current) over local file."""
    if url:
        try:
            req = urllib.request.Request(url)
            if _GH_TOKEN:
                req.add_header("Authorization", f"Bearer {_GH_TOKEN}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
    if path:
        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return []


def _fmt_run(entry: dict | None) -> dict | None:
    if entry is None:
        return None
    # normalize: older logs use {"status": "success"/"error"}, newer use {"success": bool}
    if "status" not in entry:
        entry = {**entry, "status": "success" if entry.get("success") else "error"}
    ts = entry.get("timestamp", "")
    try:
        dt_utc = _dt.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        # EST = UTC-5, EDT = UTC-4 (rough DST: second Sun Mar → first Sun Nov)
        month = dt_utc.month
        is_edt = 3 <= month <= 11  # close enough for display purposes
        et_offset = timedelta(hours=-4 if is_edt else -5)
        dt_et = dt_utc + et_offset
        label = "EDT" if is_edt else "EST"
        friendly = dt_et.strftime("%-m/%-d/%Y %-I:%M %p") + f" {label}"
    except ValueError:
        friendly = ts
    return {**entry, "friendly_time": friendly}


def _load_projects() -> list[dict]:
    try:
        with open(PROJECTS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_projects(projects: list[dict]) -> None:
    with open(PROJECTS_FILE, "w") as f:
        json.dump(projects, f, indent=2)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@app.route("/api/projects", methods=["GET"])
def get_projects():
    return jsonify(_load_projects())


@app.route("/api/projects", methods=["POST"])
def create_project():
    data = request.get_json(force=True)
    projects = _load_projects()
    base_id = _slugify(data.get("title", "untitled")) or "project"
    new_id = base_id + "-" + uuid.uuid4().hex[:8]
    while any(p["id"] == new_id for p in projects):
        new_id = base_id + "-" + uuid.uuid4().hex[:8]
    new_project = {
        "id": new_id,
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "priority": data.get("priority", "Medium"),
        "ease": data.get("ease", "Medium"),
        "frequency": data.get("frequency", "Monthly"),
        "status": data.get("status", "Planned"),
    }
    projects.append(new_project)
    _save_projects(projects)
    return jsonify(new_project), 201


@app.route("/api/projects/<project_id>", methods=["PATCH"])
def update_project(project_id):
    projects = _load_projects()
    for project in projects:
        if project["id"] == project_id:
            data = request.get_json(force=True)
            allowed = {"title", "description", "priority", "ease", "frequency", "status"}
            for key, value in data.items():
                if key in allowed:
                    project[key] = value
            _save_projects(projects)
            return jsonify(project)
    return jsonify({"error": "not found"}), 404


@app.route("/api/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    projects = _load_projects()
    updated = [p for p in projects if p["id"] != project_id]
    if len(updated) == len(projects):
        return jsonify({"error": "not found"}), 404
    _save_projects(updated)
    return jsonify({"ok": True})


@app.route("/restart", methods=["POST"])
def restart_server():
    subprocess.Popen([
        "bash", "-c",
        "sleep 1 && launchctl stop com.mathnasium.dashboard && sleep 1 && launchctl start com.mathnasium.dashboard"
    ])
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(port=8080, debug=False)
