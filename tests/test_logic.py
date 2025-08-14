
import json
from pathlib import Path
from pricing_engine import price_quote

def test_basic_generation(tmp_path: Path = Path(".")):
    tx = "4 m² bathroom; lay new ceramic floor tiles; Located in Marseille."
    q = price_quote(tx)
    assert q["zones"][0]["area_m2"] == 4.0
    assert any(t["task"] == "tiling_floor" for t in q["zones"][0]["tasks"])
    assert q["confidence"]["score"] >= 0.7
