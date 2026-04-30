import io
import json
import os
import sys
import importlib
import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _make_xlsx_bytes():
    rows = [
        {"Student Name": "Alice Smith", "Date": f"04/{d:02d}/2026", "Center": "Englewood"}
        for d in range(1, 9)
    ] + [
        {"Student Name": "Alice Smith", "Date": f"03/{d:02d}/2026", "Center": "Englewood"}
        for d in range(1, 8)
    ] + [
        {"Student Name": "Alice Smith", "Date": f"02/{d:02d}/2026", "Center": "Englewood"}
        for d in range(1, 6)
    ] + [
        {"Student Name": "Bob Jones", "Date": f"04/{d:02d}/2026", "Center": "Teaneck"}
        for d in range(1, 4)
    ]
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf.read()


def _make_csv_bytes():
    rows = [
        {"Student Name": "Alice Smith", "Center Name": "Englewood",
         "Appointment Date": f"May {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
        for d in range(1, 9)
    ] + [
        {"Student Name": "Alice Smith", "Center Name": "Englewood",
         "Appointment Date": f"Jun {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
        for d in range(1, 9)
    ] + [
        {"Student Name": "Bob Jones", "Center Name": "Teaneck",
         "Appointment Date": f"May {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
        for d in range(1, 5)
    ] + [
        {"Student Name": "Bob Jones", "Center Name": "Teaneck",
         "Appointment Date": f"Jun {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
        for d in range(1, 5)
    ]
    return pd.DataFrame(rows).to_csv(index=False).encode()


@pytest.fixture
def client(tmp_path, monkeypatch):
    projects_file = tmp_path / "future_projects.json"
    projects_file.write_text("[]")
    monkeypatch.setenv("PROJECTS_FILE", str(projects_file))
    import server
    importlib.reload(server)
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def test_scheduling_report_page(client):
    resp = client.get("/scheduling-report")
    assert resp.status_code == 200
    assert b"Scheduling Report" in resp.data


def test_run_returns_json_structure(client):
    resp = client.post(
        "/api/scheduling-report/run",
        data={
            "workout_plan": (io.BytesIO(_make_xlsx_bytes()), "workout_plan.xlsx"),
            "appointy": (io.BytesIO(_make_csv_bytes()), "appointy.csv"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "needs" in data
    assert "manual" in data
    assert "good" in data
    assert "recent_months" in data
    assert "future_months" in data
    assert "warning_center" in data
    assert "token" in data


def test_run_sets_cookie(client):
    resp = client.post(
        "/api/scheduling-report/run",
        data={
            "workout_plan": (io.BytesIO(_make_xlsx_bytes()), "workout_plan.xlsx"),
            "appointy": (io.BytesIO(_make_csv_bytes()), "appointy.csv"),
        },
        content_type="multipart/form-data",
    )
    assert "sched_token" in resp.headers.get("Set-Cookie", "")


def test_email_endpoint_calls_send_report(client, monkeypatch):
    # First run to populate cache
    client.post(
        "/api/scheduling-report/run",
        data={
            "workout_plan": (io.BytesIO(_make_xlsx_bytes()), "workout_plan.xlsx"),
            "appointy": (io.BytesIO(_make_csv_bytes()), "appointy.csv"),
        },
        content_type="multipart/form-data",
    )
    calls = []
    import scheduling_deliver
    monkeypatch.setattr(scheduling_deliver, "send_report", lambda c, r: calls.append(c))

    resp = client.post("/api/scheduling-report/email/Englewood")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    assert calls == ["Englewood"]


def test_email_endpoint_no_token_returns_400(client):
    resp = client.post("/api/scheduling-report/email/Englewood")
    assert resp.status_code == 400


def test_email_invalid_center_returns_400(client, monkeypatch):
    # Populate cache first
    client.post(
        "/api/scheduling-report/run",
        data={
            "workout_plan": (io.BytesIO(_make_xlsx_bytes()), "workout_plan.xlsx"),
            "appointy": (io.BytesIO(_make_csv_bytes()), "appointy.csv"),
        },
        content_type="multipart/form-data",
    )
    resp = client.post("/api/scheduling-report/email/InvalidCenter")
    assert resp.status_code == 400
