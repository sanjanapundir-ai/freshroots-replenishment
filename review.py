"""Monthly check: are the rules working, and do overrides add value?

    python3 review.py --sales path/to/latest/weekly_sales.csv

For every past run it compares the system forecast with what actually sold (WAPE, bias),
and for every logged decision it compares the system quantity and Raghav's final quantity
with the hindsight-ideal order-up-to quantity (Forecast Value Added). Decisions whose
outcome window hasn't fully passed yet are skipped.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import engine
from approve import LOG, OUT, ROOT


class Actuals(engine.Forecast):
    def __init__(self, weeks):
        self.weeks = weeks

    def week(self, i):
        return self.weeks[i] if i < len(self.weeks) else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sales", default=str(ROOT / "data" / "weekly_sales.csv"))
    args = ap.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text())

    sales = defaultdict(dict)
    for r in engine.read_csv(args.sales, ["SKU_ID", "Week", "Units_Sold"]):
        sales[r["SKU_ID"]][engine.iso_week_monday(r["Week"])] = float(r["Units_Sold"])

    decisions = {}
    if LOG.exists():
        with open(LOG, newline="") as f:
            for row in csv.DictReader(f):
                decisions[(row["run_id"], row["sku"])] = row

    acc = defaultdict(lambda: [0.0, 0.0, 0.0])  # run -> abs err, err, actual
    fva_rows = []
    for path in sorted(OUT.glob("*/run.json")):
        data = json.loads(path.read_text())
        meta = data["meta"]
        if meta["stops"]:
            continue
        start = engine.iso_week_monday_of(date.fromisoformat(meta["inventory_as_of"]))
        for r in data["recs"]:
            if r.get("avg_12w") is None:
                continue
            h = sales.get(r["sku"], {})
            actual = []
            while start + timedelta(weeks=len(actual)) in h:
                actual.append(h[start + timedelta(weeks=len(actual))])
            fc = engine.Forecast(r["avg_12w"], start, cfg)
            for i, a in enumerate(actual[:4]):
                acc[meta["run_id"]][0] += abs(fc.week(i) - a)
                acc[meta["run_id"]][1] += fc.week(i) - a
                acc[meta["run_id"]][2] += a

            d = decisions.get((meta["run_id"], r["sku"]))
            pol = cfg["policy"]["perishable" if r["perishable"] else "standard"]
            lt = r["lead_time_weeks"]
            if d is None or len(actual) < lt + pol["target_weeks"]:
                continue
            ideal, _ = engine.order_up_to(Actuals(actual), r["on_hand"], lt, pol["target_weeks"], 1)
            sys_q, final_q = int(d["system_qty"]), int(d["final_qty"])
            fva_rows.append({
                "run_id": meta["run_id"], "sku": r["sku"], "decision": d["decision"],
                "reason_code": d["reason_code"], "system_qty": sys_q, "final_qty": final_q,
                "hindsight_qty": ideal, "system_error": abs(sys_q - ideal), "final_error": abs(final_q - ideal),
                "override_helped": "" if d["decision"] == "APPROVE" else
                                   ("YES" if abs(final_q - ideal) < abs(sys_q - ideal) else
                                    "SAME" if abs(final_q - ideal) == abs(sys_q - ideal) else "NO"),
            })

    print("Forecast accuracy by run (first 4 weeks after each run)")
    if not any(v[2] for v in acc.values()):
        print("  No actuals after any run yet. Re-run once new weekly sales are exported.")
    for run_id, (ae, e, a) in sorted(acc.items()):
        if a:
            print(f"  {run_id}: WAPE {100 * ae / a:.1f}%  bias {100 * e / a:+.1f}%")

    print("\nForecast Value Added (overrides vs system)")
    overrides = [x for x in fva_rows if x["decision"] != "APPROVE"]
    if not overrides:
        print("  No overrides with a full outcome window yet.")
    by_reason = defaultdict(list)
    for x in overrides:
        by_reason[x["reason_code"] or "none"].append(x)
    for reason, xs in sorted(by_reason.items()):
        helped = sum(x["override_helped"] == "YES" for x in xs)
        print(f"  {reason:20} {len(xs):3} overrides, helped {helped}/{len(xs)}; "
              f"avg error system {sum(x['system_error'] for x in xs) / len(xs):.0f} vs "
              f"final {sum(x['final_error'] for x in xs) / len(xs):.0f} units")

    if fva_rows:
        out = OUT / f"monthly_review_{datetime.now():%Y-%m-%d}.csv"
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(fva_rows[0]))
            w.writeheader()
            w.writerows(fva_rows)
        print(f"\nDetail: {out}")


if __name__ == "__main__":
    main()
