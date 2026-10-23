import numpy as np
from scipy.linalg import hadamard


def _paley_hadamard(q: int) -> np.ndarray:
    residues = {i * i % q for i in range(1, q)}
    chi = np.zeros((q, q), dtype=int)
    for i in range(q):
        for j in range(q):
            d = (j - i) % q
            chi[i, j] = 1 if d in residues else -1
    np.fill_diagonal(chi, -1)
    h = np.ones((q + 1, q + 1), dtype=int)
    h[1:, 1:] = chi
    return h


_PALEY_QS = [11, 19, 23, 31, 43, 47, 59, 67, 71, 79, 83]


def _runs_for_factors(n_factors: int) -> int:
    needed = max(8, n_factors + 1)
    for n in [4, 8, 12, 16, 20, 24, 32, 36, 40, 48, 52, 56, 60, 64]:
        if n >= needed:
            return n
    raise ValueError("no suitable Plackett-Burman size found")


def generate_plackett_burman(n_factors: int) -> np.ndarray:
    if n_factors < 2:
        raise ValueError("Plackett-Burman requires at least 2 factors")
    if n_factors > 47:
        raise ValueError("Plackett-Burman supports up to 47 factors")
    n = _runs_for_factors(n_factors)
    if (n & (n - 1)) == 0:
        h = np.where(hadamard(n) > 0, 1, -1).astype(int)
    elif (n - 1) in _PALEY_QS:
        h = _paley_hadamard(n - 1)
    else:
        raise ValueError(f"unsupported Plackett-Burman size {n}")
    return h[:, 1:][:, :n_factors]


def plackett_burman_runs(n_factors: int) -> int:
    return _runs_for_factors(n_factors)
