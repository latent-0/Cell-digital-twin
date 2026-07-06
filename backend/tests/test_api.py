"""API smoke tests (Phase 3 scaffolding)."""

from fastapi.testclient import TestClient

from celltwin.api.app import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_list_endpoints():
    assert "hepatocyte" in client.get("/cells").json()
    toxins = client.get("/toxins").json()
    assert any(t["id"] == "rotenone" for t in toxins)


def test_graph_endpoint():
    g = client.get("/cells/hepatocyte/graph").json()
    assert len(g["nodes"]) > 0 and len(g["edges"]) > 0


def test_simulate_endpoint():
    ic50 = client.get("/dose-response/rotenone").json()["ic50"]
    body = {"exposures": [{"toxin_id": "rotenone", "dose": ic50 * 30}], "duration_h": 24}
    res = client.post("/simulate", json=body).json()
    assert res["final_viability"] < 0.1
    assert res["mechanism"]["dominant"] == "energy failure"


def test_dose_response_endpoint():
    res = client.get("/dose-response/rotenone").json()
    assert res["ic50"] is not None
    assert len(res["curve"]) > 5


def test_unknown_toxin_404():
    body = {"exposures": [{"toxin_id": "nope", "dose": 1.0}]}
    assert client.post("/simulate", json=body).status_code == 404
