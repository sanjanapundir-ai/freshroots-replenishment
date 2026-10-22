"""Run the replenishment engine on an SAP export.

    python3 run.py                       # data/ -> outputs/<run_id>/
    python3 run.py --data path/to/export --as-of 2026-10-22

Exit code 2 means a data check stopped the run: no recommendations were produced.
"""
import argparse
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path

import engine

ROOT = Path(__file__).parent

REC_COLS = ["sku", "name", "segment", "perishable", "vendor", "region", "route", "action", "suggested_qty",
            "alt_qty", "on_hand", "avg_12w", "avg_4w", "trend_pct", "fcst_next_week", "fcst_6w",
            "cover_weeks", "cover_no_uplift", "cover_after_order", "min_weeks", "max_weeks",
            "lead_time_weeks", "lead_time_assumed", "lead_time_demand", "safety_stock", "flags", "reasons"]
COMPARE_COLS = ["sku", "name", "aw_flags", "aw_action", "aw_qty", "aw_cover", "aw_cover_after",
                "flags", "action", "suggested_qty", "cover_weeks", "cover_after_order", "differs"]


def write_csv(path, rows, cols):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def flat(r):
    r = dict(r)
    r["flags"] = "+".join(r["flags"]) or "OK"
    r["reasons"] = " | ".join(r["reasons"])
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data"))
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--as-of", help="run date, YYYY-MM-DD (default today)")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    run_date = date.fromisoformat(args.as_of) if args.as_of else date.today()
    meta, recs = engine.run(args.data, cfg, run_date)

    run_id = f"{run_date}_{datetime.now():%H%M%S}"
    out = ROOT / "outputs" / run_id
    out.mkdir(parents=True, exist_ok=True)
    meta["run_id"] = run_id

    lines = [f"Run {run_id}  (inventory as of {meta['inventory_as_of']})", ""]
    lines += ["STOP: " + s for s in meta["stops"]]
    lines += [f"SKU {k}: {'; '.join(v)}" for k, v in meta["sku_issues"].items()]
    lines += ["WARN: " + w for w in meta["warnings"]]
    if len(lines) == 2:
        lines.append("All data checks passed.")
    (out / "data_checks.txt").write_text("\n".join(lines) + "\n")

    if meta["stops"]:
        (out / "run.json").write_text(json.dumps({"meta": meta, "recs": []}, indent=1))
        print("\n".join(lines))
        print(f"\nRun STOPPED by data checks. Nothing recommended. See {out / 'data_checks.txt'}")
        sys.exit(2)

    flat_recs = [flat(r) for r in recs]
    for r in flat_recs:
        r["differs"] = "YES" if (r.get("aw_action"), r.get("aw_qty")) != (r["action"], r["suggested_qty"]) else ""
    write_csv(out / "recommendations.csv", flat_recs, REC_COLS)
    write_csv(out / "review_queue.csv", [r for r in flat_recs if r["route"] in ("REVIEW", "BLOCKED")], REC_COLS)
    write_csv(out / "parallel_run_compare.csv", flat_recs, COMPARE_COLS)
    (out / "kpi_baseline.json").write_text(json.dumps(meta["kpi"], indent=1))
    (out / "run.json").write_text(json.dumps({"meta": meta, "recs": recs}, indent=1, default=str))
    (ROOT / "outputs" / "latest.txt").write_text(run_id)

    counts = {}
    for r in recs:
        counts[r["route"]] = counts.get(r["route"], 0) + 1
    print("\n".join(lines))
    print(f"\n{len(recs)} SKUs: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    print(f"{'SKU':7} {'route':8} {'action':6} {'qty':>5} {'cover':>6}  flags")
    for r in recs:
        if r["route"] != "PASS":
            qty = "" if r["suggested_qty"] is None else r["suggested_qty"]
            print(f"{r['sku']:7} {r['route']:8} {r['action']:6} {qty:>5} {r.get('cover_weeks', ''):>6}  "
                  f"{'+'.join(r['flags'])}")
    print(f"\nOutputs: {out}\nReview queue: python3 approve.py")


if __name__ == "__main__":
    main()
