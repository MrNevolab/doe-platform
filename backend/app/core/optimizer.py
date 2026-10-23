import itertools

import numpy as np


def _desirability(y: float, goal: str, target: float, low: float, high: float) -> float:
    lo, hi = low, high
    if hi <= lo:
        return 1.0
    if goal == "maximize":
        return float(np.clip((y - lo) / (hi - lo), 0, 1))
    if goal == "minimize":
        return float(np.clip((hi - y) / (hi - lo), 0, 1))
    if goal == "target":
        if y == target:
            return 1.0
        if y < target:
            return float(np.clip((y - lo) / (target - lo), 0, 1)) if target > lo else 0.0
        return float(np.clip((hi - y) / (hi - target), 0, 1)) if hi > target else 0.0
    raise ValueError(f"unknown goal {goal}")


def optimize(
    factors: list[dict],
    fitted: dict,
    response_name: str,
    goal: str = "maximize",
    target: float | None = None,
    grid_points: int = 21,
) -> dict:
    k = len(factors)
    terms = [("intercept", [])] + [(c["term"], c["coef"]) for c in fitted["coefficients"]]
    intercept = fitted["intercept"]

    def parse(term: str) -> list[tuple[int, int]]:
        parts = term.split("*")
        idxs = []
        for p in parts:
            if "^" in p:
                base, exp = p.split("^")
                idxs.append((int(base[1:]) - 1, int(exp)))
            else:
                idxs.append((int(p[1:]) - 1, 1))
        return idxs

    def predict(point: np.ndarray) -> float:
        y = intercept
        for c in fitted["coefficients"]:
            val = 1.0
            for i, exp in parse(c["term"]):
                val *= point[i] ** exp
            y += c["coef"] * val
        return y

    axes = [np.linspace(-1, 1, grid_points) for _ in range(k)]
    grid = np.array(list(itertools.product(*axes))) if k <= 4 else None
    if grid is None:
        axes = [np.linspace(-1, 1, grid_points)] + [
            np.zeros(grid_points) for _ in range(k - 1)
        ]
        grid = np.array(list(itertools.product(*axes)))

    preds = np.array([predict(p) for p in grid])
    lo, hi = float(preds.min()), float(preds.max())
    tgt = target if target is not None else (lo + hi) / 2
    des = np.array([_desirability(p, goal, tgt, lo, hi) for p in preds])
    best = int(np.argmax(des))

    best_point = grid[best]
    best_real = {}
    for i, f in enumerate(factors):
        mid = (f["low"] + f["high"]) / 2
        half = (f["high"] - f["low"]) / 2
        best_real[f["name"]] = float(mid + best_point[i] * half)

    return {
        "response": response_name,
        "goal": goal,
        "best_predicted": float(preds[best]),
        "best_coded": {f"p{i+1}": float(best_point[i]) for i in range(k)},
        "best_setpoints": best_real,
        "predicted_range": [lo, hi],
        "desirability": float(des[best]),
    }
