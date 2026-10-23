import itertools

import numpy as np


def coded_matrix_full(k: int) -> np.ndarray:
    return np.array(list(itertools.product([-1, 1], repeat=k)), dtype=int)


def _column_product(base: np.ndarray, cols: tuple[int, ...]) -> np.ndarray:
    col = np.ones(len(base), dtype=int)
    for c in cols:
        col = col * base[:, c]
    return col


def _achievable_resolution(base: np.ndarray, generators: list[tuple[int, ...]]) -> int:
    n_base = base.shape[1]
    word_lengths = []
    for r in range(1, len(generators) + 1):
        for combo in itertools.combinations(range(len(generators)), r):
            letters = set()
            for gi in combo:
                letters ^= set(generators[gi]) | {n_base + gi}
            if letters:
                word_lengths.append(len(letters))
    return min(word_lengths) if word_lengths else 99


def _search_fraction(k: int, resolution: int) -> np.ndarray:
    gen_len = resolution - 1
    for p in range(k - 1, 0, -1):
        n_base = k - p
        if n_base < gen_len:
            continue
        base = coded_matrix_full(n_base)
        pool = list(itertools.combinations(range(n_base), gen_len))
        if len(pool) < p:
            continue
        for gens in itertools.combinations(pool, p):
            if _achievable_resolution(base, list(gens)) >= resolution:
                cols = [base]
                for g in gens:
                    cols.append(_column_product(base, g))
                return np.column_stack(cols)
    raise ValueError(f"no resolution {resolution} design found for {k} factors")


def generate_full_factorial(k: int) -> np.ndarray:
    if k < 1:
        raise ValueError("at least one factor is required")
    if k > 15:
        raise ValueError("full factorial supports up to 15 factors")
    return coded_matrix_full(k)


def generate_fractional_factorial(k: int, resolution: int) -> np.ndarray:
    if k < 3:
        raise ValueError("fractional factorial requires at least 3 factors")
    if k > 12:
        raise ValueError("fractional factorial supports up to 12 factors")
    if resolution not in (3, 4, 5):
        raise ValueError("resolution must be 3, 4 or 5")
    try:
        return _search_fraction(k, resolution)
    except ValueError:
        if resolution > 3:
            return _search_fraction(k, resolution - 1)
        raise
