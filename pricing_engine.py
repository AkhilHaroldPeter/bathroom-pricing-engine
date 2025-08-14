
import json, re, math, argparse, logging, csv
from pathlib import Path
from datetime import datetime

from pricing_logic.material_db import MaterialDB
from pricing_logic.labor_calc import estimate, city_multiplier, LaborRate
from pricing_logic import labor_calc
from pricing_logic.vat_rules import vat_for_task
from pricing_logic.pricing_graph import topo_sort, implied_requirements
from pricing_logic.supplier_stub import get_tile_price
from pricing_logic.market import Market

OUTPUT_PATH = Path(__file__).resolve().parents[0] / "output" / "sample_quote.json"
LOG_PATH = Path(__file__).resolve().parents[0] / "logs" / "engine.log"
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
DATA_PATH = Path(__file__).resolve().parents[0] / "data"

# Simple feedback memory file
FEEDBACK_PATH = DATA_PATH / "feedback_memory.json"

DEFAULT_MARGIN = 0.18           # 18% blended margin
MIN_MARGIN = 0.12               # protect minimum
MAX_MARGIN = 0.30               # ceiling to stay competitive

TASK_MAP = {
    "demolition_tiles": ["remove the old tiles","remove old tiles","demo tiles","tile removal"],
    "plumbing_shower": ["redo the plumbing for the shower","plumbing for the shower","shower plumbing","redo plumbing"],
    "toilet_replace": ["replace the toilet","toilet"],
    "vanity_install": ["install a vanity","vanity"],
    "painting_walls": ["repaint the walls","paint the walls","repainting","painting"],
    "tiling_floor": ["lay new ceramic floor tiles","floor tiles","tiling"]
}

def infer_area_m2(text: str) -> float | None:
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:m2|m²|sqm|square meters?)', text, re.I)
    if m:
        return float(m.group(1))
    # fallback for "small 4m²" style
    m = re.search(r'(\d+(?:\.\d+)?)\s*m\s*[²2]', text, re.I)
    return float(m.group(1)) if m else None

def infer_city(text: str) -> str | None:
    m = re.search(r'located in ([A-Za-zÀ-ÿ\- ]+)', text, re.I)
    return m.group(1).strip() if m else None

def is_budget_conscious(text: str) -> bool:
    return bool(re.search(r'budget[- ]?conscious|tight budget|cost sensitive', text, re.I))

def detect_tasks(text: str) -> list[str]:
    tasks = set()
    low = text.lower()
    for t, phrases in TASK_MAP.items():
        for p in phrases:
            if p in low:
                tasks.add(t)
                break
    # heuristic extras
    if "toilet" in low: tasks.add("toilet_replace")
    if "vanity" in low: tasks.add("vanity_install")
    return list(tasks)

def wall_area_from_bath(area_m2: float) -> float:
    # Approximate wall paintable area for a small bath: 2.2m height, 60% perimeter exposed.
    # For 4 m², assume ~8 m perimeter -> ~10.5 m2 paintable.
    # Simple proportional model: wall_area ≈ area_m2 * 2.6
    return round(area_m2 * 2.6, 2)

def quantity_for_task(task: str, area_m2: float) -> float:
    if task in ("tiling_floor", "demolition_tiles"):
        return area_m2
    if task == "painting_walls":
        return wall_area_from_bath(area_m2)
    # "each" tasks
    return 1.0

def suspicious_flags(text: str) -> list[str]:
    flags = []
    if "kitchen" in text.lower() and "bath" in text.lower():
        flags.append("Mixed scopes (kitchen+bath) in one room")
    if not infer_area_m2(text):
        flags.append("Missing area")
    if not detect_tasks(text):
        flags.append("No recognized tasks")
    return flags

def confidence_score(text: str) -> float:
    score = 0.5
    if infer_area_m2(text): score += 0.2
    if detect_tasks(text): score += 0.2
    if infer_city(text): score += 0.05
    if is_budget_conscious(text): score += 0.05
    flags = suspicious_flags(text)
    score -= min(len(flags) * 0.1, 0.3)
    return max(0.0, min(1.0, round(score, 2)))

def load_feedback():
    if FEEDBACK_PATH.exists():
        try:
            return json.loads(FEEDBACK_PATH.read_text())
        except Exception:
            return {}
    return {}


def per_city_task_multiplier(city: str, task: str) -> float:
    fb = load_feedback()
    key = f"{city.lower()}::{task}"
    data = fb.get("per_city_task", {}).get(key, {})
    # Learned multiplier bounded in [0.85, 1.15]
    return max(0.85, min(1.15, data.get("multiplier", 1.0)))

def learn_city_task_multiplier(city: str, task: str, actual_hours: float, estimated_hours: float):
    fb = load_feedback()
    key = f"{city.lower()}::{task}"
    fb.setdefault("per_city_task", {}).setdefault(key, {"multiplier": 1.0, "n": 0})
    rec = fb["per_city_task"][key]
    ratio = (actual_hours / estimated_hours) if estimated_hours > 0 else 1.0
    # Exponential moving average with mild learning rate
    rec["multiplier"] = max(0.85, min(1.15, 0.8 * rec["multiplier"] + 0.2 * ratio))
    rec["n"] = rec.get("n", 0) + 1
    FEEDBACK_PATH.write_text(json.dumps(fb, indent=2))

def apply_feedback_tweaks(margin: float) -> float:
    fb = load_feedback()
    # naive scheme: if last 5 quotes mostly rejected, reduce margin slightly
    hist = fb.get("history", [])[-5:]
    if not hist:
        return margin
    accept_ratio = sum(1 for h in hist if h.get("accepted")) / len(hist)
    if accept_ratio < 0.4:
        margin = max(MIN_MARGIN, margin - 0.02)
    elif accept_ratio > 0.8:
        margin = min(MAX_MARGIN, margin + 0.02)
    return margin

def record_feedback(quote_id: str, accepted: bool):
    fb = load_feedback()
    fb.setdefault("history", []).append({
        "quote_id": quote_id,
        "accepted": accepted,
        "ts": datetime.utcnow().isoformat()
    })
    FEEDBACK_PATH.write_text(json.dumps(fb, indent=2))

def price_quote(transcript: str, market: Market | None = None, scenario: str = "mid") -> dict:
    area = infer_area_m2(transcript) or 4.0
    city = infer_city(transcript) or "Marseille"
    tasks = detect_tasks(transcript)
    tasks = list(dict.fromkeys(tasks + implied_requirements(tasks)))
    tasks = topo_sort(tasks)
    if not tasks:
        tasks = ["tiling_floor","painting_walls"]  # sensible defaults

    budget_mode = is_budget_conscious(transcript)
    market = market or Market()
    scen = scenario_multipliers(scenario)

    # Margin policy
    margin = DEFAULT_MARGIN * (0.9 if budget_mode else 1.0)
    margin += market.margin_bump() + scen['margin']
    margin = max(MIN_MARGIN, min(MAX_MARGIN, margin))
    margin = apply_feedback_tweaks(margin)

    # Pricing
    mdb = MaterialDB()
    zone = {
        "zone_name": "Bathroom",
        "area_m2": area,
        "city": city,
        "city_index": city_multiplier(city),
        "tasks": []
    }

    total_net = 0.0
    total_vat = 0.0
    total_gross = 0.0

    for task in tasks:
        qty = quantity_for_task(task, area)
        # If budget-conscious, slightly reduce material spec cost for tiles/vanity
        material_cost = mdb.cost(task, qty)
        if task == 'tiling_floor':
            supplier = get_tile_price(city)
            # Blend internal DB with supplier anchor (70/30)
            per_unit = material_cost / max(qty,1.0)
            blended = 0.7 * per_unit + 0.3 * supplier.unit_price_eur
            material_cost = blended * qty
        # Scenario & market effects on materials
        material_cost *= market.material_multiplier() * scen['material']
        if budget_mode and task in ("tiling_floor","vanity_install","toilet_replace"):
            material_cost *= 0.9  # cheaper spec

        # learnable per-city-task multiplier on hours
        lm = per_city_task_multiplier(city, task)
        labor_cost, hours = estimate(task, qty, city=city, complexity=lm, rate=LaborRate())
        labor_cost *= market.labor_multiplier() * scen['labor']

        net = (material_cost + labor_cost) * (1.0 + margin)
        vat_rate = vat_for_task(task, {"city": city})
        vat_amt = net * vat_rate
        gross = net + vat_amt

        task_block = {
            "task": task,
            "quantity": round(qty,2),
            "unit_material_desc": mdb.describe(task),
            "labor": {
                "hours": round(hours,2),
                "cost": round(labor_cost,2)
            },
            "materials": {
                "cost": round(material_cost,2)
            },
            "pricing": {
                "margin": margin,
                "net_price": round(net,2),
                "vat_rate": vat_rate,
                "vat_amount": round(vat_amt,2),
                "total_price": round(gross,2),
            },
            "estimated_duration_days": max(1, math.ceil(hours / 6.0)), # small-team/day unit
        }
        zone["tasks"].append(task_block)

        total_net += net
        total_vat += vat_amt
        total_gross += gross

    quote = {
        "quote_id": f"Q-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "created_utc": datetime.utcnow().isoformat(),
        "system": "Donizo Smart Pricing Engine (demo)",
        "currency": "EUR",
        "zones": [zone],
        "totals": {
            "net_price": round(total_net,2),
            "vat_amount": round(total_vat,2),
            "total_price": round(total_gross,2)
        },
        "assumptions": {
            "transcript_area_m2": infer_area_m2(transcript),
            "defaults_applied": True if not infer_area_m2(transcript) else False,
            "budget_conscious": budget_mode,
            "city": city
        },
        "confidence": {
            "score": confidence_score(transcript),
            "flags": suspicious_flags(transcript)
        }
    }
    # Compute trust score post-assembly
    quote['trust'] = advanced_trust_score(quote)
    return quote



def factor_scores(quote: dict) -> dict:
    """Return granular trust/confidence factors."""
    z = quote["zones"][0]
    scores = {
        "data_completeness": 0.0,
        "price_reasonability": 0.0,
        "market_volatility": 0.0,
        "historical_accuracy": 0.0
    }
    # completeness
    if z.get("area_m2") and z.get("city") and z.get("tasks"):
        scores["data_completeness"] = 0.9
    # price reasonability: ensure VAT exists and margins within policy
    margins = [t["pricing"]["margin"] for t in z["tasks"]]
    if margins and all(0.12 <= m <= 0.30 for m in margins):
        scores["price_reasonability"] = 0.85
    # volatility (penalize if recent feedback shows low acceptance)
    fb = load_feedback()
    hist = fb.get("history", [])[-10:]
    if not hist:
        scores["market_volatility"] = 0.7
        scores["historical_accuracy"] = 0.6
    else:
        accept_ratio = sum(1 for h in hist if h.get("accepted")) / len(hist)
        scores["market_volatility"] = 0.6 + 0.4*accept_ratio
        scores["historical_accuracy"] = 0.5 + 0.5*accept_ratio
    return {k: round(v,2) for k,v in scores.items()}

def advanced_trust_score(quote: dict) -> dict:
    factors = factor_scores(quote)
    overall = round(sum(factors.values())/len(factors), 2)
    return {"score": overall, "factors": factors}

def trust_score(quote: dict) -> float:
    # Factors: presence of city, supplier anchor for tiles, bounded margins, realistic durations
    score = 0.6
    z = quote["zones"][0]
    if z.get("city"): score += 0.05
    # Supplier anchor: adjust if we have a supplier tile price close to our materials
    for t in z["tasks"]:
        if t["task"] == "tiling_floor":
            supplier = get_tile_price(z["city"])
            mat = t["materials"]["cost"] / max(t["quantity"], 1.0)
            if 0.6 * supplier.unit_price_eur <= mat <= 1.4 * supplier.unit_price_eur:
                score += 0.1
    # Check margin within policy
    margins = [t["pricing"]["margin"] for t in z["tasks"]]
    if all(0.12 <= m <= 0.30 for m in margins): score += 0.05
    # Duration sanity (not zero, not extreme)
    if all(1 <= t["estimated_duration_days"] <= 10 for t in z["tasks"]): score += 0.05
    return round(min(1.0, score), 2)



def scenario_multipliers(level: str) -> dict:
    """Return multipliers for Low/Mid/High scenarios on material, labor, and margin."""
    level = level.lower()
    if level == "low":
        return {"material": 0.95, "labor": 0.92, "margin": -0.02}
    if level == "high":
        return {"material": 1.08, "labor": 1.10, "margin": +0.02}
    return {"material": 1.0, "labor": 1.0, "margin": 0.0}

def export_csv(quote: dict, path: Path):
    """Export a flat CSV of task-level breakdown."""
    rows = []
    zone = quote["zones"][0]
    for t in zone["tasks"]:
        rows.append({
            "zone": zone["zone_name"],
            "city": zone["city"],
            "task": t["task"],
            "quantity": t["quantity"],
            "labor_hours": t["labor"]["hours"],
            "labor_cost": t["labor"]["cost"],
            "materials_cost": t["materials"]["cost"],
            "margin": t["pricing"]["margin"],
            "vat_rate": t["pricing"]["vat_rate"],
            "vat_amount": t["pricing"]["vat_amount"],
            "total_price": t["pricing"]["total_price"]
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)



def main():
    """
    CLI entrypoint:
      --scenario low|mid|high (default: all three)
      --seasonality peak|off|neutral
      --inflation 0.0-0.2
      --shortage 0.0-1.0
      --transcript "text"
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["low","mid","high","all"], default="all")
    parser.add_argument("--seasonality", choices=["peak","off","neutral"], default="neutral")
    parser.add_argument("--inflation", type=float, default=0.0)
    parser.add_argument("--shortage", type=float, default=0.0)
    parser.add_argument("--transcript", type=str, default=(
        "Client wants to renovate a small 4m² bathroom. They’ll remove the old tiles, "
        "redo the plumbing for the shower, replace the toilet, install a vanity, "
        "repaint the walls, and lay new ceramic floor tiles. Budget-conscious. Located in Marseille."
    ))
    args, _unknown = parser.parse_known_args()

    market = Market(inflation=args.inflation, seasonality=args.seasonality, shortage=args.shortage)

    scenarios = ["low","mid","high"] if args.scenario == "all" else [args.scenario]
    outputs = []
    for scen in scenarios:
        quote = price_quote(args.transcript, market=market, scenario=scen)
        out_path = Path(__file__).resolve().parents[0] / "output" / f"quote_{scen}.json"
        out_path.write_text(json.dumps(quote, indent=2, ensure_ascii=False))
        csv_path = Path(__file__).resolve().parents[0] / "output" / f"quote_{scen}.csv"
        export_csv(quote, csv_path)
        outputs.append((scen, out_path, csv_path))
        logger.info(f"Generated scenario={scen} json={out_path} csv={csv_path} trust={quote['trust']} totals={quote['totals']}")

    # For convenience keep sample_quote.json pointing to mid
    mid = [o for o in outputs if o[0] == "mid"]
    if mid:
        (Path(__file__).resolve().parents[0] / "output" / "sample_quote.json").write_text(
            (mid[0][1]).read_text()
        )

    print("✅ Generated scenarios:")
    for s, jp, cp in outputs:
        print(f"  - {s.upper()}: {jp} | {cp}")

if __name__ == "__main__":
    main()
