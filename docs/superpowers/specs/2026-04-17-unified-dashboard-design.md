# Unified Dashboard Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge the automations home page and the reports page into a single unified dashboard, add a fully editable Future Projects backlog table, and move Fantasy Baseball to a separate Personal Projects page.

**Architecture:** Single-page Flask app at `/`. Live Automations table replaces the card grid + reports table. Future Projects table reads/writes `future_projects.json` via a small REST API. Fantasy Baseball moves to `/personal`.

**Tech Stack:** Flask, Jinja2, vanilla JS (fetch + inline editing), JSON file for project persistence.

---

## Files

| File | Action | Purpose |
|---|---|---|
| `server.py` | Modify | Add `/personal` route, `/api/projects` CRUD, update `/` and `/reports` routes, add CC Newsletter to REPORTS |
| `templates/index.html` | Rewrite | Unified page: Live Automations table + Future Projects table |
| `templates/personal.html` | Create | Fantasy Baseball web apps |
| `future_projects.json` | Create | Persisted project backlog data |
| `docs/superpowers/specs/2026-04-17-unified-dashboard-design.md` | Create | This file |

---

## Section 1: Routes

- `/` → unified dashboard (Live Automations + Future Projects)
- `/personal` → Personal Projects page (Fantasy Baseball)
- `/reports` → `redirect("/")` — backwards compat
- `/api/projects` → GET all projects
- `/api/projects` → POST new project
- `/api/projects/<id>` → PATCH update a project
- `/api/projects/<id>` → DELETE a project
- `/run/<script_id>` → unchanged (SSE stream)
- `/launch/<app_id>` → unchanged

---

## Section 2: Live Automations Table

Driven by the `REPORTS` registry in `server.py`. Each entry in `REPORTS` links to a `script_id` in `SCRIPTS` for the Run button.

**Add CC Newsletter to REPORTS:**
```python
{
    "id": "cc-newsletter",
    "name": "CC Newsletter Update",
    "schedule": "Monthly",
    "script_id": "cc-newsletter",
    "run_log_path": None,   # no run log yet — shows "Never" gracefully
},
```

**Table columns:**
| Column | Source |
|---|---|
| Icon + Name | `SCRIPTS[script_id].icon` + `REPORTS.name` |
| Description | `SCRIPTS[script_id].description` |
| Schedule | `REPORTS.schedule` |
| Last Auto Run | run log (status badge + friendly ET time) |
| Last Manual Run | run log (status badge + friendly ET time) |
| Delivery | Drive link + "Emailed" badge if last run succeeded |
| Run Now button | triggers `/run/<script_id>` SSE, same confirm-prompt logic as today |

`_load_run_log` already handles missing files gracefully (returns `[]`). `run_log_path: None` needs a guard: `if path: _load_run_log(path)`.

---

## Section 3: Future Projects Table

### Data model (`future_projects.json`)

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
  ...
]
```

IDs are slugified titles, generated on creation. All 10 projects from the user's list are pre-loaded.

### Dropdown options

| Field | Options |
|---|---|
| Priority | High, Medium, Low |
| Ease | Easy, Medium, Hard |
| Frequency | Daily, Weekly, Monthly, Ad-hoc |
| Status | Planned, In Progress, Live |

### Pre-loaded projects (in order as provided)

1. Monthly Terminations — Monthly — High
2. Monthly Hold — Monthly — High
3. Hold Reminder Emails — Monthly — High (7-day and 3-day reminders before end of month)
4. Birthdays & Level Ups — Monthly — Medium
5. Binder Audit — Monthly — High (MC count + last LP update check)
6. Automate Current Students Spreadsheet — Monthly — Medium
7. KPI Dashboard — Ad-hoc — High (currently "New Lead Tracking Report 1-12-26")
8. Weekly Lead Tracking Dashboard — Weekly — Medium (last week, 2 weeks ago, 3–5 week buckets)
9. Monthly Appointy Calendar Check — Monthly — Low (last week of month)
10. Assessment Email Generator — Ad-hoc — Medium
11. Monthly Revenue Changes — Monthly — Medium (last week of month + first week of month)

### API endpoints

**GET /api/projects** — returns full JSON array

**POST /api/projects** — body: `{title, description, priority, ease, frequency, status}` — appends with generated id, returns new object

**PATCH /api/projects/<id>** — body: any subset of fields — updates in place, saves file, returns updated object

**DELETE /api/projects/<id>** — removes by id, saves file, returns `{"ok": true}`

### Inline editing behavior

- Each editable cell renders as its current value in display mode
- On click, the cell switches to an `<input>` (text fields) or `<select>` (dropdowns)
- On blur or `Enter`, fires `PATCH /api/projects/<id>` with the changed field
- On success, re-renders the cell in display mode with the new value
- **"+ Add Project"** button at bottom of table: fires `POST /api/projects` with blank defaults, appends the new row in edit mode
- **🗑 delete button** on each row: fires `DELETE /api/projects/<id>`, removes the row from the DOM

### Priority / Status badge colors

| Value | Color |
|---|---|
| High / Hard | red (`#dc2626`) |
| Medium | amber (`#d97706`) |
| Low / Easy | green (`#16a34a`) |
| Planned | gray |
| In Progress | blue |
| Live | green |

---

## Section 4: Personal Projects Page (`/personal`)

Simple page at `/personal` with the existing Fantasy Baseball card grid (web apps). Header includes "← Back to Dashboard" link. No other changes to existing Fantasy Baseball functionality.

---

## Section 5: Navigation

- Main dashboard header: title on left, **"Personal Projects →"** link on right (replaces current "📊 Reports" link)
- Personal Projects header: title on left, **"← Dashboard"** link on right

---

## Out of Scope

- Authentication / access control
- Drag-to-reorder projects
- Edit UI for Live Automations table (schedule, name, etc.)
- Auto-promoting a Future Project to Live Automations
