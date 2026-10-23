import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.routes import app
from app.core.factorial import (
    generate_fractional_factorial,
    generate_full_factorial,
)
from app.core.generator import generate_design
from app.core.models import DesignRequest, Factor
from app.core.plackett_burman import generate_plackett_burman
from app.core.rsm import generate_box_behnken, generate_central_composite

client = TestClient(app)


def make_factors(n):
    return [Factor(name=f"X{i+1}", low=-1.0, high=1.0) for i in range(n)]


class TestFactorial:
    def test_full_factorial_shape(self):
        m = generate_full_factorial(4)
        assert m.shape == (16, 4)
        assert set(m.flatten()) <= {-1, 1}

    def test_full_factorial_requires_factors(self):
        with pytest.raises(ValueError):
            generate_full_factorial(0)

    def test_fractional_resolution_3(self):
        m = generate_fractional_factorial(5, 3)
        assert m.shape[1] == 5
        assert len(m) < 32

    def test_fractional_invalid(self):
        with pytest.raises(ValueError):
            generate_fractional_factorial(2, 3)
        with pytest.raises(ValueError):
            generate_fractional_factorial(5, 6)


class TestPlackettBurman:
    def test_pb_12_runs(self):
        m = generate_plackett_burman(8)
        assert m.shape[0] in (12,)
        assert m.shape[1] == 8

    def test_pb_min_factors(self):
        with pytest.raises(ValueError):
            generate_plackett_burman(1)

    def test_pb_levels(self):
        m = generate_plackett_burman(11)
        assert set(m.flatten()) <= {-1, 1}


class TestRsm:
    def test_ccd_rotatable(self):
        m = generate_central_composite(3, alpha="rotatable", center_points=4)
        assert m.shape[1] == 3
        assert len(m) == 8 + 6 + 4

    def test_ccd_face_centered(self):
        m = generate_central_composite(2, alpha="face_centered", center_points=2)
        assert np.all(np.abs(m) <= 1.0)

    def test_bb_shape(self):
        m = generate_box_behnken(3, center_points=3)
        assert m.shape == (15, 3)

    def test_bb_min_factors(self):
        with pytest.raises(ValueError):
            generate_box_behnken(2)


class TestGenerator:
    def test_design_output(self):
        req = DesignRequest(
            design_type="full_factorial",
            factors=[
                Factor(name="Temp", unit="C", low=20, high=80),
                Factor(name="pH", unit="", low=2, high=10),
            ],
            randomize=False,
        )
        d = generate_design(req)
        assert d["n_runs"] == 4
        assert d["n_factors"] == 2
        temps = [r["factors"]["Temp"] for r in d["runs"]]
        assert 20 in temps and 80 in temps

    def test_replicates(self):
        req = DesignRequest(
            design_type="full_factorial",
            factors=make_factors(2),
            replicates=2,
            randomize=False,
        )
        d = generate_design(req)
        assert d["n_runs"] == 8

    def test_blocks_must_divide(self):
        req = DesignRequest(
            design_type="full_factorial",
            factors=make_factors(2),
            blocks=3,
        )
        with pytest.raises(ValueError):
            generate_design(req)


class TestApi:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_list_types(self):
        r = client.get("/designs/types")
        assert r.status_code == 200
        assert len(r.json()) == 5

    def test_create_design(self):
        payload = {
            "design_type": "plackett_burman",
            "factors": [
                {"name": "Temp", "low": 20, "high": 80},
                {"name": "Rpm", "low": 200, "high": 800},
                {"name": "Vol", "low": 1, "high": 5},
            ],
            "randomize": True,
            "seed": 42,
        }
        r = client.post("/designs", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["n_runs"] >= 4
        assert len(body["runs"]) == body["n_runs"]

    def test_export_csv(self):
        payload = {
            "design_type": "full_factorial",
            "factors": [{"name": "A", "low": 0, "high": 10}],
            "randomize": False,
        }
        r = client.post("/designs/export?fmt=csv", json=payload)
        assert r.status_code == 200
        assert "run_id,block,status,A" in r.text

    def test_invalid_design_returns_422(self):
        payload = {"design_type": "box_behnken", "factors": [{"name": "A", "low": 0, "high": 1}]}
        r = client.post("/designs", json=payload)
        assert r.status_code == 422


class TestApiKeyAuth:
    def test_no_key_required_when_unset(self, monkeypatch):
        monkeypatch.delenv("DOE_API_KEY", raising=False)
        r = client.post("/designs", json={"design_type": "full_factorial",
                                          "factors": [{"name": "A", "low": 0, "high": 1}]})
        assert r.status_code == 200

    def test_rejects_missing_key_when_set(self, monkeypatch):
        monkeypatch.setenv("DOE_API_KEY", "secret123")
        r = client.post("/designs", json={"design_type": "full_factorial",
                                          "factors": [{"name": "A", "low": 0, "high": 1}]})
        assert r.status_code == 401

    def test_rejects_wrong_key(self, monkeypatch):
        monkeypatch.setenv("DOE_API_KEY", "secret123")
        r = client.post("/designs", json={"design_type": "full_factorial",
                                          "factors": [{"name": "A", "low": 0, "high": 1}]},
                         headers={"X-API-Key": "wrong"})
        assert r.status_code == 401

    def test_accepts_valid_key(self, monkeypatch):
        monkeypatch.setenv("DOE_API_KEY", "secret123")
        r = client.post("/designs", json={"design_type": "full_factorial",
                                          "factors": [{"name": "A", "low": 0, "high": 1}]},
                         headers={"X-API-Key": "secret123"})
        assert r.status_code == 200


class TestStatusTracking:
    def _create(self, **kw):
        payload = {"design_type": "full_factorial",
                   "factors": [{"name": "A", "low": 0, "high": 10},
                               {"name": "B", "low": 1, "high": 5}]}
        payload.update(kw)
        r = client.post("/designs", json=payload)
        assert r.status_code == 200
        return r.json()

    def test_design_has_status_fields(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DOE_DATA_DIR", str(tmp_path))
        from app.api import store as s
        s.store.data_dir = str(tmp_path)
        d = self._create()
        assert all(r["status"] == "pending" for r in d["runs"])
        assert d["design_id"]

    def test_patch_run_status(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DOE_DATA_DIR", str(tmp_path))
        from app.api import store as s
        s.store.data_dir = str(tmp_path)
        d = self._create()
        r = client.patch(f"/designs/{d['design_id']}/runs/1",
                         json={"status": "done"})
        assert r.status_code == 200
        assert r.json()["status"] == "done"
        r = client.get(f"/designs/{d['design_id']}")
        assert r.json()["runs"][0]["status"] == "done"

    def test_patch_rejects_invalid_status(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DOE_DATA_DIR", str(tmp_path))
        from app.api import store as s
        s.store.data_dir = str(tmp_path)
        d = self._create()
        r = client.patch(f"/designs/{d['design_id']}/runs/1",
                         json={"status": "banana"})
        assert r.status_code == 422

    def test_design_status_summary(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DOE_DATA_DIR", str(tmp_path))
        from app.api import store as s
        s.store.data_dir = str(tmp_path)
        d = self._create()
        client.patch(f"/designs/{d['design_id']}/runs/1", json={"status": "running"})
        client.patch(f"/designs/{d['design_id']}/runs/2", json={"status": "done"})
        r = client.get(f"/designs/{d['design_id']}/status")
        body = r.json()
        assert body["status_counts"] == {"pending": 2, "running": 1, "done": 1}
        assert body["complete"] is False

    def test_unknown_design_404(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DOE_DATA_DIR", str(tmp_path))
        from app.api import store as s
        s.store.data_dir = str(tmp_path)
        r = client.get("/designs/doesnotexist")
        assert r.status_code == 404

    def test_export_csv_contains_status(self):
        r = client.post("/designs/export?fmt=csv", json={
            "design_type": "full_factorial",
            "factors": [{"name": "A", "low": 0, "high": 10}],
            "randomize": False})
        assert "run_id,block,status,A" in r.text


class TestAnalysis:
    def _design_with_results(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DOE_DATA_DIR", str(tmp_path))
        from app.api import store as s
        s.store.data_dir = str(tmp_path)
        r = client.post("/designs", json={
            "design_type": "full_factorial",
            "factors": [{"name": "A", "low": 0, "high": 10},
                        {"name": "B", "low": 1, "high": 5}],
            "randomize": False})
        d = r.json()
        for i, run in enumerate(d["runs"]):
            a = (run["factors"]["A"] - 5) / 5
            b = (run["factors"]["B"] - 3) / 2
            y = 10 + 3 * a + 2 * b
            client.post(f"/designs/{d['design_id']}/results",
                        json={"run_id": run["run_id"], "response": "yield", "value": y})
        return d

    def test_add_result_marks_done(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DOE_DATA_DIR", str(tmp_path))
        from app.api import store as s
        s.store.data_dir = str(tmp_path)
        r = client.post("/designs", json={
            "design_type": "full_factorial",
            "factors": [{"name": "A", "low": 0, "high": 10}], "randomize": False})
        d = r.json()
        r = client.post(f"/designs/{d['design_id']}/results",
                        json={"run_id": 1, "response": "yield", "value": 72.5})
        assert r.status_code == 200
        assert r.json()["results"]["yield"] == 72.5
        assert r.json()["status"] == "done"

    def test_linear_fit_recovers_coefficients(self, monkeypatch, tmp_path):
        d = self._design_with_results(monkeypatch, tmp_path)
        r = client.post(f"/designs/{d['design_id']}/analyze",
                        json={"response": "yield", "model": "linear"})
        assert r.status_code == 200
        fit = r.json()
        assert abs(fit["intercept"] - 10) < 1e-6
        coefs = {c["term"]: c["coef"] for c in fit["coefficients"]}
        assert abs(coefs["x1"] - 3) < 1e-6
        assert abs(coefs["x2"] - 2) < 1e-6
        assert fit["r2"] > 0.999

    def test_model_significance(self, monkeypatch, tmp_path):
        d = self._design_with_results(monkeypatch, tmp_path)
        r = client.post(f"/designs/{d['design_id']}/analyze",
                        json={"response": "yield", "model": "linear"})
        fit = r.json()
        model_row = [a for a in fit["anova"] if a["term"] == "model"][0]
        assert model_row["p"] < 1e-6

    def test_analyze_needs_results(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DOE_DATA_DIR", str(tmp_path))
        from app.api import store as s
        s.store.data_dir = str(tmp_path)
        r = client.post("/designs", json={
            "design_type": "full_factorial",
            "factors": [{"name": "A", "low": 0, "high": 10}], "randomize": False})
        d = r.json()
        r = client.post(f"/designs/{d['design_id']}/analyze",
                        json={"response": "yield"})
        assert r.status_code == 422

    def test_optimize_finds_max(self, monkeypatch, tmp_path):
        d = self._design_with_results(monkeypatch, tmp_path)
        r = client.post(f"/designs/{d['design_id']}/optimize",
                        json={"response": "yield", "goal": "maximize", "model": "linear"})
        assert r.status_code == 200
        opt = r.json()
        assert opt["best_setpoints"]["A"] == 10.0
        assert opt["best_setpoints"]["B"] == 5.0
        assert abs(opt["best_predicted"] - 15) < 0.01
        assert opt["desirability"] == 1.0


class TestOptimizerUnit:
    def test_desirability_bounds(self):
        from app.core.optimizer import _desirability
        assert _desirability(15, "maximize", None, 5, 15) == 1.0
        assert _desirability(5, "maximize", None, 5, 15) == 0.0
        assert _desirability(10, "target", 10, 5, 15) == 1.0

    def test_quadratic_fit_recovers_optimum(self):
        from app.core.analysis import fit_model
        x = np.linspace(-1, 1, 11)
        X = np.column_stack([x, x**2])
        y = 5 - 2 * x**2
        coded = x.reshape(-1, 1)
        fit = fit_model(coded, y, "quadratic")
        q = [c for c in fit["coefficients"] if c["term"] == "x1^2"][0]
        assert abs(q["coef"] + 2) < 1e-6
