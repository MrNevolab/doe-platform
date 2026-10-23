import itertools

import numpy as np


def build_terms(k: int, model: str) -> list[tuple[str, list[int]]]:
    terms = [("intercept", [])]
    mains = [("x%d" % (i + 1), [i]) for i in range(k)]
    terms.extend(mains)
    if model in ("interaction", "quadratic"):
        for i, j in itertools.combinations(range(k), 2):
            terms.append(("x%d*x%d" % (i + 1, j + 1), [i, j]))
    if model == "quadratic":
        for i in range(k):
            terms.append(("x%d^2" % (i + 1), [i, i]))
    return terms


def design_matrix(coded: np.ndarray, model: str) -> tuple[np.ndarray, list[str]]:
    k = coded.shape[1]
    terms = build_terms(k, model)
    cols, names = [], []
    for name, idx in terms:
        col = np.ones(len(coded))
        for i in idx:
            col = col * coded[:, i]
        cols.append(col)
        names.append(name)
    return np.column_stack(cols), names


def fit_model(coded: np.ndarray, y: np.ndarray, model: str = "linear") -> dict:
    X, names = design_matrix(coded, model)
    n, p = X.shape
    if n < p:
        raise ValueError(f"not enough runs ({n}) to fit model with {p} terms")
    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ coeffs
    residuals = y - y_hat
    ss_total = float(np.sum((y - y.mean()) ** 2))
    ss_resid = float(np.sum(residuals**2))
    df_reg = p - 1
    df_resid = n - p
    if ss_total == 0:
        raise ValueError("response is constant, cannot fit model")
    r2 = 1 - ss_resid / ss_total
    adj_r2 = 1 - (1 - r2) * (n - 1) / df_resid if df_resid > 0 else float(r2)

    mse = ss_resid / df_resid if df_resid > 0 else 0.0
    se = np.sqrt(np.diag(np.linalg.pinv(X.T @ X)) * mse) if df_resid > 0 else np.zeros(p)
    t_stats = np.divide(coeffs, se, out=np.zeros(p), where=se > 0)

    anova_rows = []
    ss_model = ss_total - ss_resid
    f_stat = (ss_model / df_reg) / mse if df_reg > 0 and mse > 0 else 0.0
    from scipy import stats as sps

    p_model = float(1 - sps.f.cdf(f_stat, df_reg, df_resid)) if df_resid > 0 and f_stat > 0 else 1.0
    anova_rows.append(
        {
            "term": "model",
            "df": df_reg,
            "ss": ss_model,
            "ms": ss_model / df_reg if df_reg > 0 else 0.0,
            "f": f_stat,
            "p": p_model,
        }
    )
    anova_rows.append(
        {
            "term": "residual",
            "df": df_resid,
            "ss": ss_resid,
            "ms": mse,
            "f": None,
            "p": None,
        }
    )

    q2 = loo_q2(coded, y, model)

    coefficients = []
    for i, name in enumerate(names):
        if name == "intercept":
            continue
        t = float(t_stats[i])
        p_val = float(2 * (1 - sps.t.cdf(abs(t), df_resid))) if df_resid > 0 else 1.0
        coefficients.append(
            {
                "term": name,
                "coef": float(coeffs[i]),
                "se": float(se[i]),
                "t": t,
                "p": p_val,
            }
        )

    return {
        "model": model,
        "n_runs": n,
        "n_terms": p,
        "intercept": float(coeffs[0]),
        "coefficients": sorted(coefficients, key=lambda c: abs(c["coef"]), reverse=True),
        "anova": anova_rows,
        "r2": float(r2),
        "adj_r2": float(adj_r2),
        "q2": float(q2),
        "rmse": float(np.sqrt(mse)),
    }


def loo_q2(coded: np.ndarray, y: np.ndarray, model: str) -> float:
    n = len(y)
    if n < 3:
        return 0.0
    press = 0.0
    total = 0.0
    mean_all = y.mean()
    for i in range(n):
        mask = np.arange(n) != i
        try:
            X, _ = design_matrix(coded[mask], model)
            if X.shape[0] < X.shape[1]:
                return 0.0
            c, *_ = np.linalg.lstsq(X, y[mask], rcond=None)
            Xi, _ = design_matrix(coded[i : i + 1], model)
            pred = float(Xi @ c)
        except Exception:
            return 0.0
        press += (y[i] - pred) ** 2
        total += (y[i] - mean_all) ** 2
    if total == 0:
        return 0.0
    return float(1 - press / total)


def coded_from_real(factors: list[dict], run_factors: dict) -> np.ndarray:
    row = []
    for f in factors:
        lo, hi = f["low"], f["high"]
        mid = (lo + hi) / 2
        half = (hi - lo) / 2
        row.append(0.0 if half == 0 else (run_factors[f["name"]] - mid) / half)
    return np.array(row)
