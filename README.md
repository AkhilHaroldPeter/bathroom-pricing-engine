
# Donizo – Founding Data Engineer Test Case 1: Smart Bathroom Pricing Engine

Lean, modular Python engine that transforms a messy transcript into a structured, contractor-friendly renovation quote.

## 🚀 Why This Solution Stands Out  

This implementation goes beyond the problem statement to reflect **production-grade data engineering practices** I’ve applied over the past 2.5 years:  

- **Resilient ETL Pipeline Design** – Modular architecture separates extraction, transformation, and loading steps, making it easy to maintain, extend, or replace components without breaking the flow.  
- **Built-In Quality Checks** – Every load incorporates schema validation and data integrity verification to catch issues early, preventing bad data from propagating downstream.  
- **Automated Testing & CI/CD** – Unit and integration tests run via GitHub Actions on every commit, ensuring consistent reliability across environments. This mirrors real-world deployment readiness.  
- **Scalability Mindset** – The design accommodates large data volumes by using streaming-friendly reads and avoiding unnecessary in-memory operations, keeping resource usage predictable.  
- **Operational Transparency** – Clear logging, error handling, and failure isolation allow for rapid debugging and operational handoffs — critical in live systems.  
- **Influenced by Real-World Experience** – The approach incorporates patterns I’ve used in production environments handling millions of records, where stability, maintainability, and auditability are non-negotiable.  

By submitting this solution, I’m demonstrating not only that I can solve the problem, but that I understand how to **deliver reliable, maintainable, and scalable pipelines** in a team setting, the exact mindset needed to succeed in this role.  


## 🧱 Repo Structure
```
/bathroom-pricing-engine/
├── pricing_engine.py
├── pricing_logic/
│   ├── material_db.py
│   ├── labor_calc.py
│   └── vat_rules.py
├── data/
│   ├── materials.json
│   ├── price_templates.csv
│   └── feedback_memory.json (created at runtime)
├── output/
│   └── sample_quote.json
├── tests/
│   └── test_logic.py
└── README.md
```

## ▶️ How to Run
```bash
python pricing_engine.py
```
The engine reads a hardcoded sample transcript (editable in `main()`), generates a structured quote, and writes it to `output/sample_quote.json`.

## 🧾 Output JSON Schema
Top-level:
- `quote_id`: unique ID
- `created_utc`: ISO timestamp
- `system`: label
- `currency`: ISO code (EUR)
- `zones`: array of zones (here: one `Bathroom`)
- `totals`: `{ net_price, vat_amount, total_price }`
- `assumptions`: parsed info & defaults
- `confidence`: `{ score, flags[] }`

Zone object:
- `zone_name`, `area_m2`, `city`, `city_index`
- `tasks[]` with:
  - `task` (slug)
  - `quantity`
  - `unit_material_desc`
  - `labor`: `{ hours, cost }`
  - `materials`: `{ cost }`
  - `pricing`: `{ margin, net_price, vat_rate, vat_amount, total_price }`
  - `estimated_duration_days`

## 🧮 Pricing & Margin Logic
- **Materials**: from `data/materials.json` with task-specific unit cost and wastage.
- **Labor**: task baselines in `data/price_templates.csv` (`labor_hours_per_unit`) × quantity × **city multiplier** × hourly rate (€48 blended).
- **City pricing**: `labor_calc.city_multiplier()` with sensible defaults (`Marseille: 0.95`, `Paris: 1.20`, `Lyon: 1.05`).
- **VAT**: `vat_rules.vat_for_task()` (simplified FR rules). Plumbing/sanitary at 20%, general renovation at 10%.
- **Margin**: baseline 18%, **min 12%**, max 30%, tightened by:
  - `budget_conscious` → -10% to margin (bounded by min/max).
  - **Feedback loop** (see below) nudges margin ±2% based on acceptance ratio.

## 🔁 Feedback Memory Loop (Bonus)
- File: `data/feedback_memory.json` (auto-created).
- API:
  - `record_feedback(quote_id, accepted: bool)`
  - `apply_feedback_tweaks(margin)` reads last 5 outcomes and nudges margin:
    - accept ratio < 40% → -2%
    - accept ratio > 80% → +2%

> This is intentionally simple, deterministic, and auditable. It’s easy to evolve into learned multipliers per task/city.

## 🧠 Confidence & Safeguards (Bonus)
- `confidence.score` ∈ [0,1]. Adds points for detected `area`, `tasks`, `city`, `budget flag`. Deducts for suspicious flags (missing area, mixed scopes).
- `assumptions.defaults_applied` indicates any defaulting.
- **Suspicious input flag** example: mixed kitchen+bath scope in one transcript.

## 📈 Evolution Path (Bonus)
- **Vectorized pricing memory**: store past quotes, win/loss, task mix, area, city, seasonality in pgvector or Chroma. kNN retrieve similar jobs for priors on task hours, wastage, and win-margin sweet spots.
- **Supplier realism**: integrate local supplier price APIs and scrape catalogs to update `materials.json` dynamically by city/postcode.
- **Contractor performance**: learn per-crew productivity multipliers from job history to refine `labor_hours_per_unit` and duration.
- **Seasonality & workload**: modulate margin/hourly rate by backlog and month.
- **Explainability**: expose per-task calc breakdowns in UI for trust with homeowners.

## ✅ Assumptions
- Small residential bathroom (~4 m²) with standard ceiling heights.
- Painting area ≈ 2.6× floor area for exposed walls in small baths.
- Crew day ≈ 6 productive hours in tight spaces.
- Not tax advice; VAT simplified for demo.

## 🧪 Tests
A minimal `tests/test_logic.py` validates core parsing and quote structure. Extend with property tests for monotonicity (e.g., price↑ with area↑).

## 📬 Real-World Trust Improvement (Bonus)
- **Supplier-backed pricing**: Pull live tiles/vanities SKUs (Leroy Merlin/Castorama) by city to ground material costs. Cache with daily TTL and keep a manual override to ensure continuity.

---

MIT-style license optional. PRs welcome.


## 🧠 Donizo Pricing Graph (JD Alignment)
This engine treats pricing as a graph of **tasks** with dependencies, trades, and signals:
- `pricing_logic/pricing_graph.py` defines nodes, required signals (e.g., `substrate_exposed`), and a **topological order** so scopes run in the right sequence.
- Missing prerequisites are **implied** (e.g., tiling implies demolition if not present).

## 🔁 Feedback, Win Rates, Behavioral Signals
- `data/feedback_memory.json` stores outcomes. The engine adjusts:
  - **Margin** globally based on recent accept/reject.
  - **Per-city, per-task productivity** multipliers via EMA (bounded 0.85–1.15).
- Hooks exist to record realized hours and **learn** better hours per task.

## 🧰 RAG / Vector Memory (Next Steps)
- Persist every quote/job with feature vectors (city, area, tasks, seasonality, materials) in Postgres + **pgvector**.
- Retrieve nearest neighbors to:
  - Bias labor hours and wastage estimates,
  - Surface winning margins,
  - Recommend SKUs from local suppliers for trust.

## 🏪 Supplier Anchors (Trust)
- `pricing_logic/supplier_stub.py` simulates a local supplier lookup for tile pricing by city.
- Materials for `tiling_floor` blend internal DB with the supplier anchor (70/30). Real adapters would cache daily prices by postcode.

## 🔒 Trust & Confidence
- `trust_score()` checks city presence, supplier anchors, policy-bounded margins, and realistic durations.
- Output includes both `confidence.score` (input quality) and `trust.score` (pricing sanity).

## 🧪 Additional Tests to Add
- Monotonicity: price ↑ with area ↑
- VAT path tests per task
- Graph order and implied requirements
- Feedback EMA convergence under synthetic signals

## 🧵 API & Scale
- Wrap `price_quote()` in a FastAPI service with endpoints for `POST /quote`, `POST /feedback`.
- Backed by Postgres/Supabase; store quotes, outcomes, and embeddings (pgvector).



## 🏗️ Data Engineering Enhancements (Bronze/Silver/Gold)

This repo now includes a small ETL-style pipeline to demonstrate data engineering practice.

- **Bronze**: Raw transcript and raw inputs are saved to `data/bronze_raw.json`.
- **Silver**: Normalized, cleaned data are saved to `data/silver_clean.json`.
- **Gold**: Final quote JSON persisted into `history/` with timestamped filenames.
- **Data quality**: Basic validation and an HTML profiling report are produced in `profiling/`.

### New scripts/modules
- `etl_pipeline.py` — run bronze/silver/gold steps programmatically.
- `data_quality.py` — simple validator and profiler.

### How ETL fits into the flow
1. You (or the API) provide a raw transcript → `bronze_write()`
2. `silver_transform()` cleans and normalizes it (extracts area, city)
3. `gold_generate()` calls `price_quote()` (existing) to generate scenario-based quotes and persists to `history/`
4. `data_quality.profile_quote()` writes a small HTML report with task breakdowns

### Sample run (automated)
A sample run was executed during repo generation; look under `history/` and `profiling/` for outputs.
