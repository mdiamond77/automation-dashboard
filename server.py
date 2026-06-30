"""
server.py — Mathnasium Automation Dashboard
Always-on local web server on port 8080.
"""

import json
import os
import re
import socket
import ssl
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime as _dt, timezone, timedelta

import certifi

from flask import Flask, Response, redirect, render_template, request, jsonify, stream_with_context

# Load credentials from ~/.mathnasium_env so subprocesses inherit them.
# The LaunchAgent doesn't source shell profiles, so env vars aren't available otherwise.
_ENV_FILE = os.path.expanduser("~/.mathnasium_env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

import tempfile

import scheduling_deliver
from scheduling_report import run_scheduling_report

PROJECTS_FILE = os.environ.get("PROJECTS_FILE", os.path.join(os.path.dirname(__file__), "future_projects.json"))

def _get_gh_token() -> str | None:
    for gh in ["gh", "/opt/homebrew/bin/gh", "/usr/local/bin/gh"]:
        try:
            result = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=5)
            token = result.stdout.strip()
            if token:
                return token
        except Exception:
            continue
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

SCRIPTS["monthly-revenue-changes"] = {
    "name": "Monthly Revenue Changes",
    "description": "Detects account-level revenue changes from Radius Payment Reconciliation and emails AI-narrated summaries to center directors.",
    "command": [PYTHON, "main.py", "--run-type", "month_start"],
    "cwd": "/Users/mattdiamond/radius-monthly-revenue-changes",
    "icon": "💰",
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

SCRIPTS["activity-report"] = {
    "name": "Activity Report",
    "description": "Emails a summary of completed center activities from the last 3 days, grouped by activity type.",
    "command": [PYTHON, "main.py", "--trigger", "manual"],
    "cwd": "/Users/mattdiamond/mathnasium-activity-report",
    "icon": "📋",
    "category": "Mathnasium",
    "hidden": True,
}

# ── Reports registry ──────────────────────────────────────────────────────────
# group: "emails" → Automated Emails section; "tools" → Mathnasium Tools section
REPORTS = [
    # ── Automated Emails ──────────────────────────────────────────────────────
    {
        "id": "student-page-goals",
        "name": "Student Page Goals",
        "schedule": "1st of month",
        "script_id": "page-goals",
        "group": "emails",
        "run_log_path": "/Users/mattdiamond/mathnasium-page-goals/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-page-goals/main/run_log.json",
    },
    {
        "id": "birthdays-levelups",
        "name": "Birthdays & Level Ups",
        "schedule": "1st of month",
        "script_id": "birthdays-levelups",
        "group": "emails",
        "run_log_path": "/Users/mattdiamond/mathnasium-birthdays-levelups/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-birthdays-levelups/main/run_log.json",
    },
    {
        "id": "hold-reminders",
        "name": "Hold Reminder Emails",
        "schedule": "Last Mon/Tue/Thu of month",
        "script_id": "hold-reminders",
        "group": "emails",
        "run_log_path": "/Users/mattdiamond/mathnasium-hold-reminders/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-hold-reminders/main/run_log.json",
    },
    {
        "id": "binder-audit",
        "name": "Binder Audit",
        "schedule": "15th of month",
        "script_id": "binder-audit",
        "group": "emails",
        "run_log_path": "/Users/mattdiamond/mathnasium-binder-audit/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-binder-audit/main/run_log.json",
    },
    {
        "id": "attendance-alerts",
        "name": "Attendance Alerts",
        "schedule": "Weekly (Monday)",
        "script_id": "attendance-alerts",
        "group": "emails",
        "run_log_path": "/Users/mattdiamond/mathnasium-attendance-alerts/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/mathnasium-attendance-alerts/main/run_log.json",
    },
    {
        "id": "activity-report",
        "name": "Activity Report",
        "schedule": "Nightly (preview)",
        "script_id": "activity-report",
        "group": "emails",
        "run_log_path": "/Users/mattdiamond/mathnasium-activity-report/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdmathnasiums/mathnasium-activity-report/main/run_log.json",
    },
    {
        "id": "monthly-revenue-changes",
        "name": "Monthly Revenue Changes",
        "schedule": "26th & 3rd of month",
        "script_id": "monthly-revenue-changes",
        "group": "emails",
        "run_log_path": "/Users/mattdiamond/radius-monthly-revenue-changes/run_log.json",
        "run_log_url": "https://raw.githubusercontent.com/mdiamond77/radius-monthly-revenue-changes/main/run_log.json",
    },
    # ── Mathnasium Tools ──────────────────────────────────────────────────────
    {
        "id": "radius-cc-lists",
        "name": "Radius → CC Contact Lists",
        "schedule": "Monthly",
        "script_id": "radius-cc-lists",
        "group": "tools",
        "run_log_path": None,
    },
    {
        "id": "cc-newsletter",
        "name": "CC Newsletter Update",
        "schedule": "Monthly",
        "script_id": "cc-newsletter",
        "group": "tools",
        "run_log_path": None,
    },
    {
        "id": "scheduling-report",
        "name": "Scheduling Report",
        "schedule": "Monthly",
        "script_id": None,
        "group": "tools",
        "run_log_path": None,
        "tool_link": "/scheduling-report",
        "icon": "📅",
        "description": "Identifies students who need appointments booked for the next two months.",
    },
    {
        "id": "new-enrollments",
        "name": "New Enrollments",
        "schedule": "On demand",
        "script_id": None,
        "group": "tools",
        "run_log_path": None,
        "tool_link": "/new-enrollments",
        "icon": "📈",
        "description": "New student enrollments by month with program type and amount charged.",
    },
    {
        "id": "lead-enrollment-tracker",
        "name": "Lead and Enrollment Tracker",
        "schedule": "Every Friday",
        "script_id": None,
        "group": "tools",
        "run_log_path": None,
        "tool_link": "https://docs.google.com/spreadsheets/d/11A5LI_EJK17EtlQrlYw6C95imM6IOKsgt-SgpUbd3KI",
        "icon": "📊",
        "description": "Lead funnel and enrollment trends by month and quarter. Updated automatically every Friday.",
    },
    {
        "id": "current-students-spreadsheet",
        "name": "Current Students Spreadsheet",
        "schedule": "4th of month",
        "script_id": None,
        "group": "tools",
        "run_log_path": None,
        "google_script": True,
        "icon": "📊",
        "description": "Google script that rolls over last month's data and pulls in payments made this month.",
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

# ── Scheduling report session cache ───────────────────────────────────────────
_sched_cache: dict[str, dict] = {}


@app.route("/reports")
def reports_redirect():
    return redirect("/")


@app.route("/personal")
def personal_page():
    return render_template("personal.html", web_apps=WEB_APPS)


@app.route("/")
def index():
    email_rows = []
    tool_rows = []
    for report in REPORTS:
        path = report.get("run_log_path")
        url  = report.get("run_log_url")
        log = _load_run_log(path, url) if (path or url) else []
        auto_runs   = [r for r in log if r.get("trigger") == "auto"]
        manual_runs = [r for r in log if r.get("trigger") == "manual"]
        script = SCRIPTS.get(report.get("script_id"), {})
        row = {
            **report,
            "icon":        script.get("icon") or report.get("icon", "📄"),
            "description": script.get("description") or report.get("description", ""),
            "confirm":     script.get("confirm"),
            "last_auto":   _fmt_run(auto_runs[-1]   if auto_runs   else None),
            "last_manual": _fmt_run(manual_runs[-1] if manual_runs else None),
        }
        if report.get("group") == "tools":
            tool_rows.append(row)
        else:
            email_rows.append(row)
    return render_template("index.html", email_reports=email_rows, tool_reports=tool_rows)


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
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(req, timeout=5, context=ssl_ctx) as resp:
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


# ── Scheduling Report ─────────────────────────────────────────────────────────

def _serialize_result(result: dict) -> dict:
    from datetime import datetime as _dt2

    def fmt_month(s):
        return _dt2.strptime(s, "%Y-%m").strftime("%b %Y")

    def cell_bg(count, threshold):
        if count == 0:
            return "red"
        if count < threshold:
            return "yellow"
        return ""

    def issue_text(row, future_months, threshold_type):
        if threshold_type == "good":
            return ""
        parts = []
        for col in future_months:
            count = int(row[col])
            threshold = int(row["Threshold"])
            if threshold_type == "manual":
                parts.append(f"{fmt_month(col)}: {count} scheduled")
            elif count < threshold:
                parts.append(f"{fmt_month(col)}: {count} (need {threshold})")
        return " | ".join(parts)

    def df_records(df, group_key):
        records = []
        for _, row in df.iterrows():
            threshold = int(row["Threshold"])
            future_months = result["future_months"]
            records.append({
                "name": str(row["Student Name"]),
                "center": str(row["Center"]),
                "sessions": [int(row[m]) for m in result["recent_months"]],
                "threshold": threshold,
                "threshold_type": str(row["ThresholdType"]),
                "future": [int(row[m]) for m in future_months],
                "future_bg": [cell_bg(int(row[m]), threshold) for m in future_months],
                "short_1": bool(row["short_1"]),
                "short_2": bool(row["short_2"]),
                "issue": issue_text(row, future_months, group_key),
            })
        return records

    return {
        "needs": df_records(result["needs"], "needs"),
        "manual": df_records(result["manual"], "manual"),
        "good": df_records(result["good"], "good"),
        "recent_months": [fmt_month(m) for m in result["recent_months"]],
        "future_months": [fmt_month(m) for m in result["future_months"]],
        "warning_center": result.get("warning_center"),
    }


@app.route("/new-enrollments")
def new_enrollments_page():
    return render_template("new_enrollments.html")


@app.route("/api/new-enrollments/run", methods=["POST"])
def new_enrollments_run():
    body = request.get_json(force=True)
    from_month = body.get("from", "")
    to_month   = body.get("to", "")
    redownload = body.get("redownload", False)

    cmd = [PYTHON, "main.py"]
    if from_month:
        cmd += ["--from", from_month]
    if to_month:
        cmd += ["--to", to_month]
    if not redownload:
        cmd.append("--no-download")

    def generate():
        try:
            process = subprocess.Popen(
                cmd,
                cwd="/Users/mattdiamond/mathnasium-new-enrollments",
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
            else:
                yield f"data: {json.dumps('__DONE__')}\n\n"
        except Exception as e:
            yield f"data: {json.dumps(f'Error: {e}')}\n\n"
            yield f"data: {json.dumps('__ERROR__')}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/new-enrollments/download/<center>")
def new_enrollments_download(center):
    from flask import send_file
    files = {
        "teaneck":   "/Users/mattdiamond/mathnasium-new-enrollments/output/NewEnrollments_Teaneck.xlsx",
        "englewood": "/Users/mattdiamond/mathnasium-new-enrollments/output/NewEnrollments_Englewood.xlsx",
    }
    path = files.get(center.lower())
    if not path or not os.path.exists(path):
        return "File not found", 404
    return send_file(path, as_attachment=True)


@app.route("/scheduling-report")
def scheduling_report_page():
    return render_template("scheduling_report.html")


@app.route("/api/scheduling-report/run", methods=["POST"])
def scheduling_report_run():
    wp_file = request.files.get("workout_plan")
    ap_file = request.files.get("appointy")
    if not wp_file or not ap_file:
        return jsonify({"error": "Both files required"}), 400

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as wp_tmp:
        wp_file.save(wp_tmp.name)
        wp_path = wp_tmp.name

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as ap_tmp:
        ap_file.save(ap_tmp.name)
        ap_path = ap_tmp.name

    try:
        result = run_scheduling_report(wp_path, ap_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(wp_path)
        except OSError:
            pass
        try:
            os.unlink(ap_path)
        except OSError:
            pass

    token = str(uuid.uuid4())
    _sched_cache[token] = result

    payload = _serialize_result(result)
    payload["token"] = token

    resp = jsonify(payload)
    resp.set_cookie("sched_token", token, samesite="Lax")
    return resp


@app.route("/api/scheduling-report/email/<center>", methods=["POST"])
def scheduling_report_email(center):
    if center not in ("Englewood", "Teaneck"):
        return jsonify({"error": "Invalid center"}), 400

    token = request.cookies.get("sched_token")
    if not token or token not in _sched_cache:
        return jsonify({"error": "No results found — please run the report first"}), 400

    result = _sched_cache[token]
    try:
        scheduling_deliver.send_report(center, result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(port=8080, debug=False)
