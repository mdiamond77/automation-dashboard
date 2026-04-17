import json
import os
import sys
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
    assert data["title"] == "Project A"


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
