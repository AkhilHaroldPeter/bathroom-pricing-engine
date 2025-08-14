
"""
ETL pipeline: bronze -> silver -> gold
- bronze: raw transcript and generated quote JSON (as-is)
- silver: cleaned, normalized dataset used for calculations
- gold: final quote with insights and persisted history
"""
import json, os, statistics
from pathlib import Path
from datetime import datetime
from pricing_engine import price_quote, load_feedback, record_feedback
from pricing_logic.material_db import MaterialDB
from pricing_logic.labor_calc import load_task_baselines

BASE = Path(__file__).resolve().parents[0]
CONFIG = (BASE / "config.yaml")

def load_config():
    import yaml
    return yaml.safe_load(CONFIG.read_text())

def bronze_write(raw, path=None):
    cfg = load_config()
    p = BASE / (path or cfg["etl"]["bronze"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
    return p

def silver_transform(bronze_path=None):
    cfg = load_config()
    p = BASE / (bronze_path or cfg["etl"]["bronze"])
    raw = json.loads(p.read_text())
    # Basic cleaning/normalization
    cleaned = {}
    cleaned["transcript"] = raw.get("transcript", "").strip()
    # normalize area unit: try to extract m2
    import re
    m = re.search(r'(\\d+(?:\\.\\d+)?)\\s*(?:m2|m²|sqm|square meters?)', cleaned["transcript"], re.I)
    if m:
        cleaned["area_m2"] = float(m.group(1))
    else:
        cleaned["area_m2"] = raw.get("area_m2") or None
    cleaned["city"] = raw.get("city") or ""
    cleaned["meta"] = raw.get("meta", {})
    # write silver
    out = BASE / cfg["etl"]["silver"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False))
    return out

def gold_generate(silver_path=None, market=None, scenario="mid"):
    cfg = load_config()
    p = BASE / (silver_path or cfg["etl"]["silver"])
    clean = json.loads(p.read_text())
    transcript = clean["transcript"]
    # Use existing price_quote (which returns rich quote) but accept market and scenario
    mk = market
    quote = price_quote(transcript, market=mk, scenario=scenario)
    # add ETL metadata
    quote["_etl"] = {"generated_at": datetime.utcnow().isoformat(), "scenario": scenario}
    # insights: simple stats
    zone = quote["zones"][0]
    quote["_insights"] = {
        "avg_task_price": round(sum(t["pricing"]["total_price"] for t in zone["tasks"]) / max(1,len(zone["tasks"])),2),
        "task_count": len(zone["tasks"])
    }
    # persist to history with timestamp
    hist_prefix = cfg["etl"]["gold_prefix"]
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    hist_path = BASE / f"{hist_prefix}_{ts}.json"
    hist_path.write_text(json.dumps(quote, indent=2, ensure_ascii=False))
    return hist_path, quote

def compare_with_previous(new_path):
    # compare latest two history files by file time (basic)
    cfg = load_config()
    hist_dir = BASE / cfg["history_path"]
    files = sorted(hist_dir.glob("quote_*.json"))
    if len(files) < 2:
        return None
    with open(files[-2]) as f:
        prev = json.load(f)
    with open(files[-1]) as f:
        curr = json.load(f)
    deltas = {}
    # compare totals
    prev_tot = prev["totals"]["total_price"]
    cur_tot = curr["totals"]["total_price"]
    pct = ((cur_tot - prev_tot)/prev_tot)*100 if prev_tot else None
    deltas["prev_total"] = prev_tot
    deltas["curr_total"] = cur_tot
    deltas["pct_change"] = round(pct,2) if pct is not None else None
    return deltas
