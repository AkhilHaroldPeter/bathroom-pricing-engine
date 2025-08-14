
"""
Market condition adjustment utilities.

This module lets you simulate macro effects on pricing:
- inflation: multiplicative factor on both materials and labor
- seasonality: e.g., peak season raises labor cost and margin slightly
- shortage: affects materials more than labor
"""
from dataclasses import dataclass

@dataclass
class Market:
    inflation: float = 0.0   # e.g., 0.05 => +5%
    seasonality: str = "neutral"  # "peak", "off", "neutral"
    shortage: float = 0.0    # 0..1 severity applied to materials cost

    def material_multiplier(self) -> float:
        m = 1.0 + self.inflation
        m *= (1.0 + 0.10*self.shortage)
        return m

    def labor_multiplier(self) -> float:
        m = 1.0 + self.inflation*0.6
        if self.seasonality == "peak":
            m *= 1.05
        elif self.seasonality == "off":
            m *= 0.98
        return m

    def margin_bump(self) -> float:
        # small policy bump during peak season to protect backlog
        if self.seasonality == "peak":
            return 0.01
        if self.seasonality == "off":
            return -0.005
        return 0.0
