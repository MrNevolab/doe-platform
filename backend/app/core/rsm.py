import itertools

import numpy as np


def generate_central_composite(
    k: int,
    alpha: str = "rotatable",
    center_points: int = 4,
    factorial_fraction_resolution: int = 5,
) -> np.ndarray:
    if k < 2:
        raise ValueError("central composite designs require at least 2 factors")
    if k > 10:
        raise ValueError("central composite designs support up to 10 factors")
    if alpha not in ("rotatable", "orthogonal", "face_centered"):
        raise ValueError("alpha must be 'rotatable', 'orthogonal' or 'face_centered'")
    if center_points < 1:
        raise ValueError("center_points must be at least 1")

    if k <= 5:
        factorial = np.array(list(itertools.product([-1, 1], repeat=k)), dtype=int)
    else:
        from .factorial import generate_fractional_factorial

        factorial = generate_fractional_factorial(k, factorial_fraction_resolution)
        while factorial.shape[0] < 2 * k + 2:
            res = factorial_fraction_resolution - 1
            if res < 3:
                factorial = np.array(list(itertools.product([-1, 1], repeat=k)), dtype=int)
                break
            factorial = generate_fractional_factorial(k, res)
            factorial_fraction_resolution = res

    if alpha == "face_centered":
        a = 1.0
    else:
        a = (factorial.shape[0]) ** (1.0 / (2 * k))
        if alpha == "orthogonal":
            a = (factorial.shape[0] * (1 + center_points**0.5 / 2) ** 2 / (k + center_points)) ** (
                1 / (2 * k)
            )

    axial = np.zeros((2 * k, k))
    for i in range(k):
        axial[2 * i, i] = a
        axial[2 * i + 1, i] = -a

    centers = np.zeros((center_points, k))
    return np.vstack([factorial, axial, centers])


def generate_box_behnken(k: int, center_points: int = 3) -> np.ndarray:
    if k < 3:
        raise ValueError("Box-Behnken designs require at least 3 factors")
    if k > 10:
        raise ValueError("Box-Behnken designs support up to 10 factors")
    if center_points < 1:
        raise ValueError("center_points must be at least 1")

    rows = []
    for i, j in itertools.combinations(range(k), 2):
        for si, sj in itertools.product([-1, 1], repeat=2):
            row = [0] * k
            row[i] = si
            row[j] = sj
            rows.append(row)
    design = np.array(rows, dtype=float)
    centers = np.zeros((center_points, k))
    return np.vstack([design, centers])
