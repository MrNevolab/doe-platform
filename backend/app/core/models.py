from enum import Enum
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, Field


class DesignType(str, Enum):
    FULL_FACTORIAL = "full_factorial"
    FRACTIONAL_FACTORIAL = "fractional_factorial"
    PLACKETT_BURMAN = "plackett_burman"
    CENTRAL_COMPOSITE = "central_composite"
    BOX_BEHNKEN = "box_behnken"


DESIGN_LABELS = {
    DesignType.FULL_FACTORIAL: "Vollfaktoriell",
    DesignType.FRACTIONAL_FACTORIAL: "Fraktionell-faktoriell",
    DesignType.PLACKETT_BURMAN: "Plackett-Burman",
    DesignType.CENTRAL_COMPOSITE: "Central Composite (RSM)",
    DesignType.BOX_BEHNKEN: "Box-Behnken (RSM)",
}


class Factor(BaseModel):
    name: str
    unit: Optional[str] = None
    low: float = Field(description="low level in real units, maps to coded -1")
    high: float = Field(description="high level in real units, maps to coded +1")

    def to_real(self, coded: float) -> float:
        return (self.low + self.high) / 2 + coded * (self.high - self.low) / 2


class FactorType(str, Enum):
    NUMERIC = "numeric"


class DesignRequest(BaseModel):
    design_type: DesignType
    factors: list[Factor] = Field(min_length=1)
    runs: Optional[int] = Field(
        default=None,
        description="target number of runs for Plackett-Burman or fraction for fractional designs",
    )
    resolution: int = Field(default=3, ge=3, le=5)
    center_points: int = Field(default=4, ge=1)
    alpha: str = Field(default="rotatable")
    randomize: bool = True
    seed: Optional[int] = None
    replicates: int = Field(default=1, ge=1)
    blocks: int = Field(default=1, ge=1)
