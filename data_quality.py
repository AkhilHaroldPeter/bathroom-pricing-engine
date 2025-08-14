
"""
Simple data quality checks and profiling to mimic a production gate.
Generates a small HTML report with basic stats.
"""
import json, statistics, os
from pathlib import Path

BASE = Path(__file__).resolve().parents[0]
CFG = BASE / "config.yaml"

def load_config():
    import yaml
    return yaml.safe_load(CFG.read_text())

def validate_silver(silver_path):
    data = json.loads(Path(silver_path).read_text())
    issues = []
    if not data.get("transcript"):
        issues.append("empty_transcript")
    if data.get("area_m2") is None:
        issues.append("missing_area")
    if not data.get("city"):
        issues.append("missing_city")
    return issues

def profile_quote(quote, out_html_path):
    # Basic profiling: task-level histogram and totals
    zone = quote["zones"][0]
    rows = []
    for t in zone["tasks"]:
        rows.append((t["task"], t["pricing"]["total_price"]))
    totals = quote["totals"]
    html = "<html><body><h1>Profiling Report</h1>"
    html += f"<p>Total price: {totals['total_price']} {quote['currency']}</p>"
    html += "<table border='1'><tr><th>task</th><th>price</th></tr>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td></tr>"
    html += "</table></body></html>"
    Path(out_html_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_html_path).write_text(html, encoding="utf-8")
    return out_html_path
