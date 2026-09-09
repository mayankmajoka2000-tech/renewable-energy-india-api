"""
Smoke tests for the FastAPI app. Run against a throwaway, in-memory-style
SQLite database (never the real bundled data) so CI doesn't need the ~12-min
ingestion pipeline. Verifies the app boots, tables are created, the states
reference table can be seeded, and every router responds with the shape
callers depend on -- catching import errors, routing typos, and schema
mismatches before they hit a real deployment.
"""
import os
import tempfile

import pytest

# Point at a fresh temp SQLite file BEFORE importing app.database / app.main,
# since the engine is created at import time.
_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(_tmp_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db_path}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.seed_states import seed  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _setup_db():
    init_db()
    db = SessionLocal()
    seed(db)
    db.close()
    yield
    os.remove(_tmp_db_path)


client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["docs"] == "/docs"


def test_docs_load():
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_openapi_schema_is_valid():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    for path in ("/states", "/emissions/units", "/capacity", "/potential",
                 "/projects", "/resource/solar-wind", "/stats/summary"):
        assert path in schema["paths"], f"missing route: {path}"


def test_states_seeded_and_served():
    resp = client.get("/states")
    assert resp.status_code == 200
    states = resp.json()
    assert len(states) == 34
    names = {s["name"] for s in states}
    assert "Maharashtra" in names
    assert "Delhi" in names


def test_stats_summary_lists_all_tables():
    resp = client.get("/stats/summary")
    assert resp.status_code == 200
    tables = {row["table"] for row in resp.json()}
    assert tables == {
        "states", "emissions/units", "emissions/grid-factor", "capacity",
        "potential", "projects", "resource/solar-wind", "emissions/avoided",
    }


def test_empty_data_tables_return_empty_lists_not_errors():
    # No CEA/MNRE/NASA data is seeded in this CI run (only states) -- every
    # data endpoint should degrade to an empty list, never a 500.
    for path in ("/emissions/units", "/capacity", "/potential", "/projects",
                 "/resource/solar-wind"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
        assert resp.json() == []


def test_projects_filters_accept_query_params():
    resp = client.get("/projects", params={
        "state": "Gujarat", "technology_group": "Solar",
        "verified_only": True, "min_capacity_mw": 5,
    })
    assert resp.status_code == 200


def test_rate_limit_headers_or_pass_through():
    # Rate limiter should not block a handful of normal requests.
    for _ in range(5):
        resp = client.get("/states")
        assert resp.status_code == 200
