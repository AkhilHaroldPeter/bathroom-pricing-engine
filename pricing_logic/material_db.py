
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "materials.json"

class MaterialDB:
    def __init__(self, path: Path = DATA_PATH):
        with open(path, "r") as f:
            self.db = json.load(f)

    def cost(self, task: str, qty: float) -> float:
        if task not in self.db:
            return 0.0
        spec = self.db[task]
        unit_cost = spec["cost_per_unit"]
        wastage = spec.get("wastage_factor", 1.0)
        return unit_cost * qty * wastage

    def describe(self, task: str) -> dict:
        return self.db.get(task, {})
