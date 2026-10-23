import os
import secrets
from typing import Optional

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

from app.api.store import store
from app.core.analysis import coded_from_real, fit_model
from app.core.generator import generate_design
from app.core.models import DESIGN_LABELS, DesignRequest, DesignType

app = FastAPI(
    title="DoE Platform API",
    version="0.2.0",
    description="Design-of-Experiments generator for lab automation (TMS XData compatible)",
)

API_KEY_ENV = "DOE_API_KEY"


def require_api_key(request: Request) -> bool:
    expected = os.environ.get(API_KEY_ENV)
    if not expected:
        return True
    provided = request.headers.get("X-API-Key", "")
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key header")
    return True


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/designs/types", dependencies=[Depends(require_api_key)])
def list_design_types():
    return [
        {"type": dt.value, "label": label}
        for dt, label in DESIGN_LABELS.items()
    ]


@app.post("/designs", dependencies=[Depends(require_api_key)])
def create_design(payload: dict, save: bool = True):
    try:
        req = DesignRequest(**payload)
        design = generate_design(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    for run in design["runs"]:
        run["status"] = "pending"
    if save:
        design = store.save(design)
    return design


@app.get("/designs/{design_id}", dependencies=[Depends(require_api_key)])
def get_design(design_id: str):
    design = store.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail=f"design {design_id} not found")
    return design


@app.patch("/designs/{design_id}/runs/{run_id}", dependencies=[Depends(require_api_key)])
def update_run_status(design_id: str, run_id: int, payload: dict):
    status = payload.get("status")
    try:
        run = store.update_run_status(design_id, run_id, status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if run is None:
        raise HTTPException(status_code=404, detail=f"design {design_id} not found")
    return run


@app.get("/designs/{design_id}/status", dependencies=[Depends(require_api_key)])
def design_status(design_id: str):
    design = store.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail=f"design {design_id} not found")
    counts = {}
    for run in design["runs"]:
        counts[run["status"]] = counts.get(run["status"], 0) + 1
    return {
        "design_id": design_id,
        "n_runs": len(design["runs"]),
        "status_counts": counts,
        "complete": counts.get("done", 0) == len(design["runs"]),
    }


@app.post("/designs/{design_id}/results", dependencies=[Depends(require_api_key)])
def add_result(design_id: str, payload: dict):
    try:
        run_id = int(payload["run_id"])
        response = payload["response"]
        value = float(payload["value"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="payload requires run_id, response, value")
    try:
        run = store.add_result(design_id, run_id, response, value)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return run


@app.post("/designs/{design_id}/analyze", dependencies=[Depends(require_api_key)])
def analyze_design(design_id: str, payload: dict):
    from app.core.analysis import coded_from_real, fit_model

    design = store.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail=f"design {design_id} not found")
    response = payload.get("response")
    model = payload.get("model", "linear")
    if model not in ("linear", "interaction", "quadratic"):
        raise HTTPException(status_code=422, detail="model must be linear, interaction or quadratic")
    if not response:
        raise HTTPException(status_code=422, detail="response is required")

    rows, ys = [], []
    for run in design["runs"]:
        if run.get("status") == "done" and response in run.get("results", {}):
            rows.append(coded_from_real(design["factors"], run["factors"]))
            ys.append(run["results"][response])
    if len(rows) < 3:
        raise HTTPException(status_code=422, detail=f"not enough completed runs with results for {response}")

    coded = np.array(rows)
    y = np.array(ys)
    try:
        fit = fit_model(coded, y, model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    fit["response"] = response
    fit["n_completed_runs"] = len(rows)
    return fit


@app.post("/designs/{design_id}/optimize", dependencies=[Depends(require_api_key)])
def optimize_design(design_id: str, payload: dict):
    from app.core.optimizer import optimize

    design = store.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail=f"design {design_id} not found")
    response = payload.get("response")
    goal = payload.get("goal", "maximize")
    model = payload.get("model", "quadratic")
    if not response:
        raise HTTPException(status_code=422, detail="response is required")
    if goal not in ("maximize", "minimize", "target"):
        raise HTTPException(status_code=422, detail="goal must be maximize, minimize or target")

    rows, ys = [], []
    for run in design["runs"]:
        if run.get("status") == "done" and response in run.get("results", {}):
            rows.append(coded_from_real(design["factors"], run["factors"]))
            ys.append(run["results"][response])
    if len(rows) < 3:
        raise HTTPException(status_code=422, detail=f"not enough completed runs with results for {response}")

    coded = np.array(rows)
    y = np.array(ys)
    try:
        fit = fit_model(coded, y, model)
        opt = optimize(design["factors"], fit, response, goal, payload.get("target"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    opt["model_fit"] = {"r2": fit["r2"], "q2": fit["q2"], "rmse": fit["rmse"]}
    return opt


@app.post("/designs/export", dependencies=[Depends(require_api_key)])
def export_design(payload: dict, fmt: str = "csv"):
    try:
        req = DesignRequest(**payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    design = generate_design(req)
    for run in design["runs"]:
        run["status"] = "pending"
    headers = [f["name"] for f in design["factors"]]
    if fmt == "csv":
        lines = ["run_id,block,status," + ",".join(headers)]
        for run in design["runs"]:
            vals = ",".join(str(run["factors"][h]) for h in headers)
            lines.append(f"{run['run_id']},{run['block']},{run['status']},{vals}")
        return Response(
            content="\n".join(lines),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=doe_design.csv"},
        )
    elif fmt == "json":
        return design
    raise HTTPException(status_code=400, detail=f"unsupported format {fmt}")


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
