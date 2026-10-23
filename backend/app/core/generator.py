import numpy as np

from .factorial import generate_fractional_factorial, generate_full_factorial
from .models import DesignRequest, DesignType
from .plackett_burman import generate_plackett_burman
from .rsm import generate_box_behnken, generate_central_composite


def _coded_matrix(req: DesignRequest) -> np.ndarray:
    k = len(req.factors)
    dt = req.design_type
    if dt == DesignType.FULL_FACTORIAL:
        if k > 12:
            raise ValueError("full factorial supports up to 12 factors")
        matrix = generate_full_factorial(k)
    elif dt == DesignType.FRACTIONAL_FACTORIAL:
        matrix = generate_fractional_factorial(k, req.resolution)
    elif dt == DesignType.PLACKETT_BURMAN:
        matrix = generate_plackett_burman(k)
    elif dt == DesignType.CENTRAL_COMPOSITE:
        matrix = generate_central_composite(
            k,
            alpha=req.alpha,
            center_points=req.center_points,
        )
    elif dt == DesignType.BOX_BEHNKEN:
        matrix = generate_box_behnken(k, center_points=req.center_points)
    else:
        raise ValueError(f"unsupported design type {dt}")
    return matrix


def generate_design(req: DesignRequest) -> dict:
    coded = _coded_matrix(req)

    if req.blocks > 1:
        if len(coded) % req.blocks != 0:
            raise ValueError(
                f"number of runs {len(coded)} cannot be split into {req.blocks} equal blocks"
            )
        per_block = len(coded) // req.blocks
        block_ids = np.repeat(np.arange(1, req.blocks + 1), per_block)
    else:
        block_ids = np.ones(len(coded), dtype=int)

    if req.replicates > 1:
        coded = np.vstack([coded] * req.replicates)
        block_ids = np.tile(block_ids, req.replicates)

    run_ids = np.arange(1, len(coded) + 1)
    if req.randomize:
        rng = np.random.default_rng(req.seed)
        order = rng.permutation(len(coded))
        coded = coded[order]
        block_ids = block_ids[order]

    factors = req.factors
    headers = [f.name for f in factors]
    units = [f.unit for f in factors]
    rows_real = []
    for row in coded:
        rows_real.append([float(f.to_real(c)) for f, c in zip(factors, row)])

    runs = []
    for i, row in enumerate(rows_real):
        runs.append(
            {
                "run_id": int(run_ids[i]),
                "block": int(block_ids[i]),
                "std_order": i + 1,
                "factors": {h: v for h, v in zip(headers, row)},
                "units": {h: u for h, u in zip(headers, units)},
            }
        )

    return {
        "design_type": req.design_type.value,
        "n_factors": len(factors),
        "n_runs": len(runs),
        "randomized": req.randomize,
        "factors": [f.model_dump() for f in factors],
        "runs": runs,
    }
