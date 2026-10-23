import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

RUN_STATUSES = ("pending", "running", "done", "failed")


class DesignStore:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.environ.get("DOE_DATA_DIR") or "/tmp/doe_designs"
        os.makedirs(self.data_dir, exist_ok=True)

    def _path(self, design_id: str) -> str:
        return os.path.join(self.data_dir, f"{design_id}.json")

    def save(self, design: dict) -> dict:
        design_id = design.get("design_id") or uuid.uuid4().hex[:12]
        design["design_id"] = design_id
        design["created_at"] = datetime.now(timezone.utc).isoformat()
        with open(self._path(design_id), "w", encoding="utf-8") as f:
            json.dump(design, f, ensure_ascii=False, indent=2)
        return design

    def get(self, design_id: str) -> Optional[dict]:
        path = self._path(design_id)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _persist(self, design: dict) -> None:
        with open(self._path(design["design_id"]), "w", encoding="utf-8") as f:
            json.dump(design, f, ensure_ascii=False, indent=2)

    def update_run_status(self, design_id: str, run_id: int, status: str) -> Optional[dict]:
        if status not in RUN_STATUSES:
            raise ValueError(f"status must be one of {RUN_STATUSES}")
        design = self.get(design_id)
        if design is None:
            return None
        for run in design["runs"]:
            if run["run_id"] == run_id:
                run["status"] = status
                run["status_updated_at"] = datetime.now(timezone.utc).isoformat()
                self._persist(design)
                return run
        raise KeyError(f"run_id {run_id} not found in design {design_id}")

    def add_result(self, design_id: str, run_id: int, response: str, value: float) -> dict:
        design = self.get(design_id)
        if design is None:
            raise KeyError(f"design {design_id} not found")
        for run in design["runs"]:
            if run["run_id"] == run_id:
                run.setdefault("results", {})[response] = float(value)
                run["status"] = "done"
                run["status_updated_at"] = datetime.now(timezone.utc).isoformat()
                self._persist(design)
                return run
        raise KeyError(f"run_id {run_id} not found in design {design_id}")


store = DesignStore()
