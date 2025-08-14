
import csv
from pathlib import Path
from dataclasses import dataclass

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "price_templates.csv"

@dataclass
class LaborRate:
    base_hourly_eur: float = 48.0  # contractor blended rate

CITY_INDEX = {
    "paris": 1.20,
    "marseille": 0.95,
    "lyon": 1.05,
    "default": 1.00
}

def city_multiplier(city: str | None) -> float:
    if not city:
        return CITY_INDEX["default"]
    key = city.strip().lower()
    return CITY_INDEX.get(key, CITY_INDEX["default"])

def load_task_baselines(path: Path = DATA_PATH):
    baselines = {}
    with open(path, "r") as f:
        for i, row in enumerate(csv.DictReader(f)):
            baselines[row["task"]] = {
                "unit": row["unit"],
                "labor_hours_per_unit": float(row["labor_hours_per_unit"]),
                "notes": row["notes"]
            }
    return baselines

def estimate(task: str, qty: float, city: str | None, complexity: float = 1.0,
             rate: LaborRate = LaborRate()) -> tuple[float, float]:
    """
    Returns: (labor_cost_eur, hours)
    """
    base = load_task_baselines().get(task)
    if not base:
        return (0.0, 0.0)
    hours = base["labor_hours_per_unit"] * qty * complexity
    hours *= city_multiplier(city)
    cost = hours * rate.base_hourly_eur
    return (cost, hours)
