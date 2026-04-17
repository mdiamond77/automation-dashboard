# Unified Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the automations home page and reports page into a single unified dashboard with a Live Automations table and a fully editable Future Projects backlog, and move Fantasy Baseball to a separate Personal Projects page.

**Architecture:** Flask app at `/Users/mattdiamond/automation-dashboard`. The unified `/` route replaces both the old home and reports pages. A new `/api/projects` REST API reads/writes `future_projects.json`. `/personal` serves the Fantasy Baseball section. `/reports` redirects to `/`.

**Tech Stack:** Flask, Jinja2, vanilla JS (fetch + inline editing), JSON file for project persistence, pytest + Flask test client for API tests.

---

## File Map

| File | Action |
|---|---|
| `future_projects.json` | Create — project backlog data |
| `server.py` | Modify — add API endpoints, update routes, add CC Newsletter to REPORTS |
| `templates/index.html` | Rewrite — unified page |
| `templates/personal.html` | Create — Fantasy Baseball page |
| `tests/test_projects_api.py` | Create — API tests |

Working directory for all commands: `/Users/mattdiamond/automation-dashboard`

Python binary: `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`

---

## Task 1: Create future_projects.json

**Files:**
- Create: `future_projects.json`

- [ ] **Step 1: Create the file**

```json
[
  {
    "id": "monthly-terminations",
    "title": "Monthly Terminations",
    "description": "",
    "priority": "High",
    "ease": "Medium",
    "frequency": "Monthly",
    "status": "Planned"
  },
  {
    "id": "monthly-hold",
    "title": "Monthly Hold",
    "description": "",
    "priority": "High",
    "ease": "Medium",
    "frequency": "Monthly",
    "status": "Planned"
  },
  {
    "id": "hold-reminder-emails",
    "title": "Hold Reminder Emails",
    "description": "7-day and 3-day reminders before end of month listing students still on hold or coming off hold, with prompt to review texts/emails/notes/calls.",
    "priority": "High",
    "ease": "Medium",
    "frequency": "Monthly",
    "status": "Planned"
  },
  {
    "id": "birthdays-level-ups",
    "title": "Birthdays & Level Ups",
    "description": "",
    "priority": "Medium",
    "ease": "Medium",
    "frequency": "Monthly",
    "status": "Planned"
  },
  {
    "id": "binder-audit",
    "title": "Binder Audit",
    "description": "Monthly check of how many MCs and last update to LPs per student.",
    "priority": "High",
    "ease": "Medium",
    "frequency": "Monthly",
    "status": "Planned"
  },
  {
    "id": "current-students-spreadsheet",
    "title": "Automate Current Students Spreadsheet",
    "description": "",
    "priority": "Medium",
    "ease": "Medium",
    "frequency": "Monthly",
    "status": "Planned"
  },
  {
    "id": "kpi-dashboard",
    "title": "KPI Dashboard",
    "description": "Automate the New Lead Tracking Report. Unclear where this lives — needs scoping.",
    "priority": "High",
    "ease": "Hard",
    "frequency": "Ad-hoc",
    "status": "Planned"
  },
  {
    "id": "weekly-lead-tracking",
    "title": "Weekly Lead Tracking Dashboard",
    "description": "Show last week's leads, 2 weeks ago, then buckets from 3–5 weeks.",
    "priority": "Medium",
    "ease": "Medium",
    "frequency": "Weekly",
    "status": "Planned"
  },
  {
    "id": "appointy-calendar-check",
    "title": "Monthly Appointy Calendar Check",
    "description": "Run last week of the month.",
    "priority": "Low",
    "ease": "Easy",
    "frequency": "Monthly",
    "status": "Planned"
  },
  {
    "id": "assessment-email-generator",
    "title": "Assessment Email Generator",
    "description": "",
    "priority": "Medium",
    "ease": "Medium",
    "frequency": "Ad-hoc",
    "status": "Planned"
  },
  {
    "id": "monthly-revenue-changes",
    "title": "Monthly Revenue Changes",
    "description": "One report last week of month, one first week of month.",
    "priority": "Medium",
    "ease": "Medium",
    "frequency": "Monthly",
    "status": "Planned"
  }
]
```

- [ ] **Step 2: Verify the file is valid JSON**

```bash
python3 -c "import json; data=json.load(open('future_projects.json')); print(f'{len(data)} projects loaded')"
```

Expected output: `11 projects loaded`

- [ ] **Step 3: Commit**

```bash
git add future_projects.json
git commit -m "feat: add future_projects.json with 11 pre-loaded projects"
```

---

## Task 2: Projects API endpoints + tests

**Files:**
- Create: `tests/test_projects_api.py`
- Modify: `server.py`

The API reads/writes `future_projects.json`. All endpoints use JSON. The test suite uses Flask's built-in test client and a temporary JSON file so it doesn't touch the real data.

- [ ] **Step 1: Create the tests file**

```python
# tests/test_projects_api.py
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SAMPLE = [
    {"id": "proj-a", "title": "Project A", "description": "Desc A",
     "priority": "High", "ease": "Easy", "frequency": "Monthly", "status": "Planned"},
    {"id": "proj-b", "title": "Project B", "description": "Desc B",
     "priority": "Low", "ease": "Hard", "frequency": "Weekly", "status": "In Progress"},
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    projects_file = tmp_path / "future_projects.json"
    projects_file.write_text(json.dumps(SAMPLE))
    monkeypatch.setenv("PROJECTS_FILE", str(projects_file))
    import importlib
    import server
    importlib.reload(server)
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def test_get_projects(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["id"] == "proj-a"


def test_post_project(client):
    resp = client.post("/api/projects", json={
        "title": "New One", "description": "", "priority": "Medium",
        "ease": "Medium", "frequency": "Ad-hoc", "status": "Planned"
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "New One"
    assert "id" in data

    all_resp = client.get("/api/projects")
    assert len(all_resp.get_json()) == 3


def test_patch_project(client):
    resp = client.patch("/api/projects/proj-a", json={"priority": "Low", "status": "In Progress"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["priority"] == "Low"
    assert data["status"] == "In Progress"
    assert data["title"] == "Project A"  # unchanged fields preserved


def test_patch_project_not_found(client):
    resp = client.patch("/api/projects/nonexistent", json={"priority": "Low"})
    assert resp.status_code == 404


def test_delete_project(client):
    resp = client.delete("/api/projects/proj-b")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}

    all_resp = client.get("/api/projects")
    ids = [p["id"] for p in all_resp.get_json()]
    assert "proj-b" not in ids


def test_delete_project_not_found(client):
    resp = client.delete("/api/projects/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — expect failures**

```bash
cd /Users/mattdiamond/automation-dashboard
mkdir -p tests
python3 -m pytest tests/test_projects_api.py -v 2>&1 | head -40
```

Expected: Several test failures mentioning missing routes.

- [ ] **Step 3: Add the projects API to server.py**

Add this import at the top of `server.py` (after existing imports):

```python
from flask import Flask, Response, redirect, render_template, request, jsonify, stream_with_context
```

Add this constant near the top of `server.py` (after the existing imports, before `app = Flask(__name__)`):

```python
PROJECTS_FILE = os.environ.get("PROJECTS_FILE", os.path.join(os.path.dirname(__file__), "future_projects.json"))
```

Add these helper functions to `server.py` after the `_fmt_run` function:

```python
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
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
```

Add these routes to `server.py` after the existing `reports_page` route:

```python
@app.route("/api/projects", methods=["GET"])
def get_projects():
    return jsonify(_load_projects())


@app.route("/api/projects", methods=["POST"])
def create_project():
    data = request.get_json(force=True)
    projects = _load_projects()
    new_project = {
        "id": _slugify(data.get("title", "untitled")) + "-" + str(len(projects)),
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
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
python3 -m pytest tests/test_projects_api.py -v
```

Expected output:
```
tests/test_projects_api.py::test_get_projects PASSED
tests/test_projects_api.py::test_post_project PASSED
tests/test_projects_api.py::test_patch_project PASSED
tests/test_projects_api.py::test_patch_project_not_found PASSED
tests/test_projects_api.py::test_delete_project PASSED
tests/test_projects_api.py::test_delete_project_not_found PASSED
6 passed
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_projects_api.py server.py
git commit -m "feat: add /api/projects CRUD endpoints"
```

---

## Task 3: Update server.py routes

**Files:**
- Modify: `server.py`

Add CC Newsletter to `REPORTS`, fix the `None` run_log_path guard, update the `/` route to serve the unified page, add `/personal`, and redirect `/reports`.

- [ ] **Step 1: Add CC Newsletter to REPORTS**

In `server.py`, find the `REPORTS` list and replace it with:

```python
REPORTS = [
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
    },
]
```

- [ ] **Step 2: Fix run_log_path None guard and update the `/` route**

Find the existing `reports_page` function and replace it entirely:

```python
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
        log = _load_run_log(path) if path else []
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
```

Also remove (delete) the old `index` function that previously rendered `index.html` with `scripts`, `web_apps`, `interactive`.

- [ ] **Step 3: Verify server starts cleanly**

```bash
cd /Users/mattdiamond/automation-dashboard
python3 -c "import server; print('OK')"
```

Expected: `OK` with no errors.

- [ ] **Step 4: Run existing tests still pass**

```bash
python3 -m pytest tests/test_projects_api.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py
git commit -m "feat: unified / route, /personal route, /reports redirect, CC Newsletter in REPORTS"
```

---

## Task 4: Create personal.html

**Files:**
- Create: `templates/personal.html`

- [ ] **Step 1: Create the template**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Personal Projects — Mathnasium Automations</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f0f2f5; color: #1a1a1a; min-height: 100vh; }

    header { background: #1e3a5f; color: white; padding: 24px 40px; display: flex; align-items: center; gap: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
    header h1 { font-size: 1.6rem; font-weight: 700; }
    header p  { font-size: 0.9rem; opacity: 0.75; margin-top: 2px; }
    .logo { font-size: 2rem; }
    .nav-link { margin-left: auto; color: rgba(255,255,255,0.8); text-decoration: none; font-size: 0.9rem; }
    .nav-link:hover { color: white; }

    main { max-width: 960px; margin: 0 auto; padding: 36px 24px; }
    h2 { font-size: 0.75rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #6b7280; margin: 0 0 16px; }

    .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
    .card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); display: flex; flex-direction: column; gap: 12px; transition: box-shadow 0.2s; }
    .card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
    .card-header { display: flex; align-items: flex-start; gap: 12px; }
    .card-icon { font-size: 1.8rem; line-height: 1; flex-shrink: 0; }
    .card-title { font-size: 1rem; font-weight: 700; color: #111; }
    .card-desc { font-size: 0.85rem; color: #6b7280; line-height: 1.5; }
    .card-footer { margin-top: auto; }
    .btn { display: inline-block; padding: 9px 20px; border-radius: 8px; font-size: 0.875rem; font-weight: 600; cursor: pointer; border: none; text-decoration: none; transition: opacity 0.15s; }
    .btn:hover { opacity: 0.85; }
    .btn-success { background: #16a34a; color: white; }
  </style>
</head>
<body>

<header>
  <div class="logo">🏆</div>
  <div>
    <h1>Personal Projects</h1>
    <p>Web apps and tools for personal use</p>
  </div>
  <a class="nav-link" href="/">← Dashboard</a>
</header>

<main>
  <h2>Fantasy Baseball</h2>
  <div class="cards">
    {% for app in web_apps %}
    <div class="card">
      <div class="card-header">
        <div class="card-icon">{{ app.icon }}</div>
        <div><div class="card-title">{{ app.name }}</div></div>
      </div>
      <div class="card-desc">{{ app.description }}</div>
      <div class="card-footer">
        <a class="btn btn-success" href="/launch/{{ app.id }}" target="_blank">↗ Open</a>
      </div>
    </div>
    {% endfor %}
  </div>
</main>

</body>
</html>
```

- [ ] **Step 2: Verify the route returns 200**

```bash
python3 -c "
import server
server.app.config['TESTING'] = True
with server.app.test_client() as c:
    r = c.get('/personal')
    print(r.status_code)
"
```

Expected: `200`

- [ ] **Step 3: Commit**

```bash
git add templates/personal.html
git commit -m "feat: add /personal page for Fantasy Baseball web apps"
```

---

## Task 5: Rewrite index.html

**Files:**
- Modify: `templates/index.html`

This is the main unified page. It has two sections: Live Automations (a table driven by server-rendered `reports`) and Future Projects (a table populated and edited via JS calling `/api/projects`).

Badge colors:
- Priority High / Ease Hard → `#dc2626` (red)
- Priority Medium / Ease Medium → `#d97706` (amber)
- Priority Low / Ease Easy → `#16a34a` (green)
- Status Planned → `#6b7280` (gray)
- Status In Progress → `#2563eb` (blue)
- Status Live → `#16a34a` (green)

- [ ] **Step 1: Replace the entire contents of templates/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Mathnasium Automations</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f0f2f5; color: #1a1a1a; min-height: 100vh; }

    header { background: #1e3a5f; color: white; padding: 24px 40px; display: flex; align-items: center; gap: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
    header h1 { font-size: 1.6rem; font-weight: 700; }
    header p  { font-size: 0.9rem; opacity: 0.75; margin-top: 2px; }
    .logo { font-size: 2rem; }
    .nav-link { margin-left: auto; color: rgba(255,255,255,0.8); text-decoration: none; font-size: 0.9rem; }
    .nav-link:hover { color: white; }

    main { max-width: 1200px; margin: 0 auto; padding: 36px 24px; }
    .section { margin-bottom: 48px; }
    h2 { font-size: 0.75rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #6b7280; margin: 0 0 16px; }

    /* ── Tables ── */
    table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
    th { background: #1e3a5f; color: white; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; padding: 12px 16px; text-align: left; white-space: nowrap; }
    td { padding: 14px 16px; border-bottom: 1px solid #f0f0f0; font-size: 0.875rem; vertical-align: middle; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #fafafa; }

    /* ── Automation table ── */
    .auto-name { display: flex; align-items: flex-start; gap: 10px; }
    .auto-icon { font-size: 1.4rem; line-height: 1; flex-shrink: 0; margin-top: 2px; }
    .auto-title { font-weight: 700; font-size: 0.9rem; }
    .auto-desc { font-size: 0.8rem; color: #6b7280; margin-top: 3px; line-height: 1.4; max-width: 280px; }

    .status-ok   { color: #16a34a; font-weight: 600; }
    .status-err  { color: #dc2626; font-weight: 600; }
    .status-none { color: #9ca3af; font-style: italic; }

    .delivery-link { color: #1e3a5f; text-decoration: none; font-weight: 500; margin-right: 8px; }
    .delivery-link:hover { text-decoration: underline; }

    .btn { display: inline-block; padding: 7px 16px; border-radius: 8px; font-size: 0.8rem; font-weight: 600; cursor: pointer; border: none; text-decoration: none; transition: opacity 0.15s; }
    .btn:hover { opacity: 0.85; }
    .btn:disabled { opacity: 0.5; cursor: default; }
    .btn-primary { background: #1e3a5f; color: white; }
    .btn-confirm { background: #16a34a; color: white; }
    .btn-cancel  { background: #e5e7eb; color: #374151; }
    .btn-add     { background: #1e3a5f; color: white; margin-top: 12px; padding: 8px 18px; font-size: 0.8rem; }

    .running-indicator { display: none; align-items: center; font-size: 0.8rem; color: #60a5fa; margin-left: 8px; }
    .running-indicator.active { display: inline-flex; }
    .spinner { display: inline-block; width: 10px; height: 10px; border: 2px solid #64748b; border-top-color: #60a5fa; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 6px; }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ── Confirm prompt ── */
    .confirm-prompt { display: flex; flex-direction: column; gap: 6px; }
    .confirm-question { font-size: 0.8rem; color: #374151; font-weight: 500; }
    .confirm-buttons { display: flex; gap: 6px; }

    /* ── Future projects table ── */
    .badge { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 0.72rem; font-weight: 700; color: white; white-space: nowrap; }

    #projects-table td { cursor: pointer; }
    #projects-table td:last-child { cursor: default; }
    #projects-table input,
    #projects-table select { width: 100%; padding: 4px 6px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.85rem; font-family: inherit; background: white; }
    #projects-table input:focus,
    #projects-table select:focus { outline: 2px solid #1e3a5f; border-color: transparent; }

    .btn-delete { background: none; border: none; color: #9ca3af; font-size: 1rem; cursor: pointer; padding: 2px 6px; border-radius: 4px; }
    .btn-delete:hover { background: #fee2e2; color: #dc2626; }

    /* ── Output panel ── */
    #output-panel { display: none; position: fixed; bottom: 0; left: 0; right: 0; height: 320px; background: #0f172a; color: #e2e8f0; font-family: "SF Mono", "Fira Code", monospace; font-size: 0.8rem; z-index: 100; flex-direction: column; box-shadow: 0 -4px 24px rgba(0,0,0,0.4); }
    #output-panel.active { display: flex; }
    #output-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 20px; background: #1e293b; border-bottom: 1px solid #334155; flex-shrink: 0; }
    #output-title  { font-weight: 700; color: #94a3b8; font-size: 0.8rem; letter-spacing: 0.05em; }
    #output-status { font-size: 0.75rem; }
    #output-close  { background: none; border: none; color: #64748b; font-size: 1.2rem; cursor: pointer; padding: 2px 6px; border-radius: 4px; }
    #output-close:hover { background: #334155; color: white; }
    #output-body   { flex: 1; overflow-y: auto; padding: 16px 20px; line-height: 1.6; }
    .output-line { white-space: pre-wrap; word-break: break-all; }
    .output-line.done  { color: #60a5fa; font-weight: bold; margin-top: 8px; }
    .output-line.error { color: #f87171; }
  </style>
</head>
<body>

<header>
  <div class="logo">🤖</div>
  <div>
    <h1>Mathnasium Automations</h1>
    <p>Live automations and project backlog</p>
  </div>
  <a class="nav-link" href="/personal">Personal Projects →</a>
</header>

<main>

  <!-- ── Live Automations ── -->
  <div class="section">
    <h2>Live Automations</h2>
    <table>
      <thead>
        <tr>
          <th>Automation</th>
          <th>Schedule</th>
          <th>Last Auto Run</th>
          <th>Last Manual Run</th>
          <th>Delivery</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {% for r in reports %}
        <tr>
          <td>
            <div class="auto-name">
              <div class="auto-icon">{{ r.icon }}</div>
              <div>
                <div class="auto-title">{{ r.name }}</div>
                <div class="auto-desc">{{ r.description }}</div>
              </div>
            </div>
          </td>
          <td>{{ r.schedule }}</td>

          <td>
            {% if r.last_auto %}
              <span class="{{ 'status-ok' if r.last_auto.status == 'success' else 'status-err' }}">
                {{ '✓' if r.last_auto.status == 'success' else '✗' }}
              </span>
              {{ r.last_auto.friendly_time }}
            {% else %}
              <span class="status-none">Never</span>
            {% endif %}
          </td>

          <td>
            {% if r.last_manual %}
              <span class="{{ 'status-ok' if r.last_manual.status == 'success' else 'status-err' }}">
                {{ '✓' if r.last_manual.status == 'success' else '✗' }}
              </span>
              {{ r.last_manual.friendly_time }}
            {% else %}
              <span class="status-none">Never</span>
            {% endif %}
          </td>

          <td>
            {% set last = r.last_auto or r.last_manual %}
            {% if last and last.drive_link %}
              <a class="delivery-link" href="{{ last.drive_link }}" target="_blank">📁 Drive</a>
            {% endif %}
            {% if last and last.status == 'success' %}
              <span style="color:#6b7280;font-size:0.8rem;">📧 Emailed</span>
            {% endif %}
            {% if not last %}
              <span class="status-none">—</span>
            {% endif %}
          </td>

          <td id="run-cell-{{ r.script_id }}" style="white-space:nowrap;">
            {% if r.confirm %}
            <button class="btn btn-primary" id="run-btn-{{ r.script_id }}"
                    onclick="askConfirm('{{ r.script_id }}', '{{ r.name }}', '{{ r.confirm }}')">▶ Run Now</button>
            {% else %}
            <button class="btn btn-primary" id="run-btn-{{ r.script_id }}"
                    onclick="runScript('{{ r.script_id }}', '{{ r.name }}')">▶ Run Now</button>
            {% endif %}
            <span class="running-indicator" id="running-{{ r.script_id }}">
              <span class="spinner"></span> Running…
            </span>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <!-- ── Future Projects ── -->
  <div class="section">
    <h2>Future Projects</h2>
    <table id="projects-table">
      <thead>
        <tr>
          <th>Title</th>
          <th>Description</th>
          <th>Priority</th>
          <th>Ease</th>
          <th>Frequency</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="projects-body"></tbody>
    </table>
    <button class="btn btn-add" onclick="addProject()">+ Add Project</button>
  </div>

</main>

<!-- ── Output Panel ── -->
<div id="output-panel">
  <div id="output-header">
    <span id="output-title">OUTPUT</span>
    <span id="output-status"></span>
    <button id="output-close" onclick="closeOutput()">✕</button>
  </div>
  <div id="output-body"></div>
</div>

<script>
  // ── Badge helpers ────────────────────────────────────────────
  const BADGE_COLORS = {
    priority: { High: "#dc2626", Medium: "#d97706", Low: "#16a34a" },
    ease:     { Easy: "#16a34a", Medium: "#d97706", Hard: "#dc2626" },
    status:   { Planned: "#6b7280", "In Progress": "#2563eb", Live: "#16a34a" },
    frequency:{}
  };

  const DROPDOWN_OPTIONS = {
    priority:  ["High", "Medium", "Low"],
    ease:      ["Easy", "Medium", "Hard"],
    frequency: ["Daily", "Weekly", "Monthly", "Ad-hoc"],
    status:    ["Planned", "In Progress", "Live"],
  };

  function badge(field, value) {
    const color = (BADGE_COLORS[field] || {})[value];
    if (!color) return value;
    return `<span class="badge" style="background:${color}">${value}</span>`;
  }

  // ── Projects table ───────────────────────────────────────────
  let projects = [];

  async function loadProjects() {
    const resp = await fetch("/api/projects");
    projects = await resp.json();
    renderProjects();
  }

  function renderProjects() {
    const tbody = document.getElementById("projects-body");
    tbody.innerHTML = "";
    projects.forEach(p => tbody.appendChild(buildRow(p)));
  }

  function buildRow(p) {
    const tr = document.createElement("tr");
    tr.dataset.id = p.id;
    tr.innerHTML = `
      <td data-field="title">${escHtml(p.title)}</td>
      <td data-field="description">${escHtml(p.description)}</td>
      <td data-field="priority">${badge("priority", p.priority)}</td>
      <td data-field="ease">${badge("ease", p.ease)}</td>
      <td data-field="frequency">${escHtml(p.frequency)}</td>
      <td data-field="status">${badge("status", p.status)}</td>
      <td><button class="btn-delete" title="Delete" onclick="deleteProject('${p.id}', this)">🗑</button></td>
    `;
    tr.querySelectorAll("td[data-field]").forEach(td => {
      td.addEventListener("click", () => startEdit(td, p.id, td.dataset.field, p[td.dataset.field]));
    });
    return tr;
  }

  function startEdit(td, projectId, field, currentValue) {
    if (td.querySelector("input,select")) return; // already editing
    const isDropdown = field in DROPDOWN_OPTIONS;
    if (isDropdown) {
      const select = document.createElement("select");
      DROPDOWN_OPTIONS[field].forEach(opt => {
        const o = document.createElement("option");
        o.value = opt; o.textContent = opt;
        if (opt === currentValue) o.selected = true;
        select.appendChild(o);
      });
      select.addEventListener("change", () => commitEdit(td, projectId, field, select.value));
      select.addEventListener("blur", () => cancelEdit(td, projectId, field, currentValue));
      td.innerHTML = "";
      td.appendChild(select);
      select.focus();
    } else {
      const input = document.createElement("input");
      input.type = "text";
      input.value = currentValue;
      input.addEventListener("keydown", e => {
        if (e.key === "Enter") commitEdit(td, projectId, field, input.value);
        if (e.key === "Escape") cancelEdit(td, projectId, field, currentValue);
      });
      input.addEventListener("blur", () => commitEdit(td, projectId, field, input.value));
      td.innerHTML = "";
      td.appendChild(input);
      input.focus();
    }
  }

  async function commitEdit(td, projectId, field, value) {
    const resp = await fetch(`/api/projects/${projectId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: value }),
    });
    const updated = await resp.json();
    // Update local cache
    const idx = projects.findIndex(p => p.id === projectId);
    if (idx !== -1) projects[idx] = updated;
    // Re-render just this cell
    const isBadge = field in BADGE_COLORS && Object.keys(BADGE_COLORS[field]).length > 0;
    td.innerHTML = isBadge ? badge(field, value) : escHtml(value);
    td.addEventListener("click", () => startEdit(td, projectId, field, value));
  }

  function cancelEdit(td, projectId, field, originalValue) {
    if (!td.querySelector("input,select")) return;
    const isBadge = field in BADGE_COLORS && Object.keys(BADGE_COLORS[field]).length > 0;
    td.innerHTML = isBadge ? badge(field, originalValue) : escHtml(originalValue);
    td.addEventListener("click", () => startEdit(td, projectId, field, originalValue));
  }

  async function addProject() {
    const resp = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "New Project", description: "", priority: "Medium", ease: "Medium", frequency: "Monthly", status: "Planned" }),
    });
    const newProject = await resp.json();
    projects.push(newProject);
    const tbody = document.getElementById("projects-body");
    tbody.appendChild(buildRow(newProject));
    // Start editing the title immediately
    const newRow = tbody.lastElementChild;
    const titleCell = newRow.querySelector("[data-field='title']");
    startEdit(titleCell, newProject.id, "title", newProject.title);
  }

  async function deleteProject(projectId, btn) {
    if (!confirm("Delete this project?")) return;
    await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
    projects = projects.filter(p => p.id !== projectId);
    btn.closest("tr").remove();
  }

  function escHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ── Run scripts ──────────────────────────────────────────────
  let currentSource = null;
  let currentScriptId = null;

  function runScript(id, name) {
    if (currentSource) currentSource.close();
    currentScriptId = id;
    const panel     = document.getElementById("output-panel");
    const body      = document.getElementById("output-body");
    const title     = document.getElementById("output-title");
    const status    = document.getElementById("output-status");
    const runBtn    = document.getElementById(`run-btn-${id}`);
    const indicator = document.getElementById(`running-${id}`);

    body.innerHTML = "";
    title.textContent = name.toUpperCase();
    status.innerHTML = '<span style="color:#60a5fa">● Running…</span>';
    panel.classList.add("active");
    if (runBtn) runBtn.disabled = true;
    if (indicator) indicator.classList.add("active");

    currentSource = new EventSource(`/run/${id}`);
    currentSource.onmessage = function(e) {
      const text = JSON.parse(e.data);
      if (text === "__DONE__") {
        status.innerHTML = '<span style="color:#4ade80">✓ Done</span>';
        addLine("✓ Completed successfully.", "done");
        finish();
        setTimeout(() => location.reload(), 1500);
        return;
      }
      if (text.startsWith("__ERROR__")) {
        status.innerHTML = '<span style="color:#f87171">✗ Failed</span>';
        addLine("✗ " + text, "error");
        finish();
        return;
      }
      addLine(text, "");
    };
    currentSource.onerror = function() {
      status.innerHTML = '<span style="color:#f87171">✗ Connection lost</span>';
      finish();
    };

    function addLine(text, cls) {
      const line = document.createElement("div");
      line.className = "output-line " + cls;
      line.textContent = text;
      body.appendChild(line);
      body.scrollTop = body.scrollHeight;
    }

    function finish() {
      currentSource.close(); currentSource = null;
      if (runBtn) runBtn.disabled = false;
      if (indicator) indicator.classList.remove("active");
    }
  }

  const _cellCache = {};

  function askConfirm(id, name, question) {
    const cell = document.getElementById(`run-cell-${id}`);
    _cellCache[id] = cell.innerHTML;
    cell.innerHTML = `
      <div class="confirm-prompt">
        <div class="confirm-question">${question}</div>
        <div class="confirm-buttons">
          <button class="btn btn-confirm" onclick="runScript('${id}', '${name}')">Yes, run it</button>
          <button class="btn btn-cancel" onclick="cancelConfirm('${id}')">Cancel</button>
        </div>
      </div>`;
  }

  function cancelConfirm(id) {
    document.getElementById(`run-cell-${id}`).innerHTML = _cellCache[id];
  }

  function closeOutput() {
    if (currentSource) { currentSource.close(); currentSource = null; }
    document.getElementById("output-panel").classList.remove("active");
    if (currentScriptId) {
      const indicator = document.getElementById(`running-${currentScriptId}`);
      if (indicator) indicator.classList.remove("active");
      currentScriptId = null;
    }
  }

  // ── Init ─────────────────────────────────────────────────────
  loadProjects();
</script>

</body>
</html>
```

- [ ] **Step 2: Verify the route returns 200 and renders both sections**

```bash
python3 -c "
import server
server.app.config['TESTING'] = True
with server.app.test_client() as c:
    r = c.get('/')
    body = r.data.decode()
    assert r.status_code == 200
    assert 'Live Automations' in body
    assert 'Future Projects' in body
    assert 'Personal Projects' in body
    print('OK')
"
```

Expected: `OK`

- [ ] **Step 3: Verify /reports redirects to /**

```bash
python3 -c "
import server
server.app.config['TESTING'] = True
with server.app.test_client() as c:
    r = c.get('/reports')
    print(r.status_code, r.headers.get('Location'))
"
```

Expected: `301 /` (or `302 /`)

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/test_projects_api.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add templates/index.html
git commit -m "feat: rewrite index.html as unified dashboard"
```

---

## Task 6: Restart server and smoke test

- [ ] **Step 1: Kill old server process and let LaunchAgent restart it**

```bash
pkill -f "server.py" || true
sleep 3
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
```

Expected: `200`

- [ ] **Step 2: Verify /personal loads**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/personal
```

Expected: `200`

- [ ] **Step 3: Verify /reports redirects**

```bash
curl -s -o /dev/null -w "%{http_code}" -L http://localhost:8080/reports
```

Expected: `200` (followed redirect to `/`)

- [ ] **Step 4: Commit tests directory**

```bash
git add tests/
git commit -m "chore: add tests directory to repo" --allow-empty
```

Actually, tests were already committed in Task 2. Just verify git status is clean:

```bash
git status
```

Expected: `nothing to commit, working tree clean`
