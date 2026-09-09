from fastapi.testclient import TestClient

from app.timetable_main import app


def test_standalone_app_exposes_timetable_product_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["product"] == "timetable"


def test_standalone_app_contains_scheduling_routes_only():
    paths = {route.path for route in app.routes}
    assert "/api/auth/login" in paths
    assert "/api/timetables/{timetable_id}" in paths
    assert "/api/solve" in paths
    assert "/api/solve/preflight/{term_id}" in paths
    assert "/api/curriculum-requirements/expand/{term_id}" in paths
    assert not any(path.startswith("/api/attendance") for path in paths)
    assert not any(path.startswith("/api/exams") for path in paths)
