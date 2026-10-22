"""Freshroots replenishment engine.

Pipeline: SAP export -> data checks -> forecast + stock cover -> rules in a fixed
order -> suggested order-up-to quantity -> routing (PASS / AUTO / REVIEW / BLOCKED).

Standard library only, so the IT team can run it anywhere Python 3.8+ exists.
"""
import csv
import io
import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

FLAG_TEXT = {
    "STOCKOUT_RISK": "Stock cover below minimum",
    "OVERSTOCK": "Stock cover above maximum",
    "HIGH_DEMAND": "Last 4 weeks > 20% above 12-week average",
    "BORDERLINE": "Cover within buffer of a threshold",
    "ASSUMPTION_SENSITIVE": "Flag changes if festival uplift is removed",
    "CONFLICT": "High demand and overstock at the same time",
    "EXPEDITE": "Stock runs out before an order placed now would arrive",
    "VOLATILE": "Z-segment: demand too erratic for rules",
    "SHELF_LIFE_RISK": "Current stock outlives shelf life",
    "DATA_ISSUE": "SKU failed a data check",
}
REVIEW_FLAGS = {"HIGH_DEMAND", "BORDERLINE", "ASSUMPTION_SENSITIVE", "CONFLICT",
                "EXPEDITE", "VOLATILE", "SHELF_LIFE_RISK"}


# ---------------------------------------------------------------- loading

REQUIRED = {
    "sku_master.csv": ["SKU_ID", "SKU_Name", "Perishability", "Standard_Reorder_Qty", "Distributor_ID"],
    "current_inventory.csv": ["SKU_ID", "Units_On_Hand", "As_Of_Date"],
    "weekly_sales.csv": ["SKU_ID", "Week", "Units_Sold"],
}


def parse_csv(text, name, required):
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        raise ValueError(f"{name} is empty")
    missing = [c for c in required if c not in rows[0]]
    if missing:
        raise ValueError(f"{name} is missing columns: {', '.join(missing)}")
    return rows


def read_csv(path, required):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return parse_csv(f.read(), path, required)


def load_inputs(data_dir):
    return tuple(read_csv(f"{data_dir}/{name}", cols) for name, cols in REQUIRED.items())


def load_texts(texts):
    """Same as load_inputs, from {filename: csv text} (the hosted upload)."""
    for name in REQUIRED:
        if not texts.get(name):
            raise ValueError(f"Missing file: {name}")
    return tuple(parse_csv(texts[name], name, cols) for name, cols in REQUIRED.items())


def iso_week_monday(week):
    """'2026-W42' -> Monday of that ISO week."""
    year, wk = week.split("-W")
    return date.fromisocalendar(int(year), int(wk), 1)


# ---------------------------------------------------------------- data checks

def check_data(master, inventory, sales, cfg, run_date):
    """Returns (stops, sku_issues, clean). Any stop halts the whole run."""
    dc = cfg["data_checks"]
    stops, sku_issues = [], defaultdict(list)
    master_ids = {r["SKU_ID"] for r in master}

    inv = {}
    inv_dates = set()
    for r in inventory:
        try:
            qty = float(r["Units_On_Hand"])
            as_of = date.fromisoformat(r["As_Of_Date"])
        except ValueError:
            stops.append(f"Unreadable inventory row for {r['SKU_ID']}: {r}")
            continue
        if qty < 0:
            stops.append(f"Negative stock for {r['SKU_ID']} ({qty:g})")
        if r["SKU_ID"] in inv:
            sku_issues[r["SKU_ID"]].append("Duplicate inventory rows (multiple locations not yet supported)")
        inv[r["SKU_ID"]] = qty
        inv_dates.add(as_of)

    if len(inv_dates) > 1:
        stops.append(f"Inventory export mixes snapshot dates: {sorted(str(d) for d in inv_dates)}")
    as_of = max(inv_dates) if inv_dates else None
    if as_of is not None:
        age = (run_date - as_of).days
        if age > dc["max_inventory_age_days"]:
            stops.append(f"Inventory snapshot is {age} days old (as of {as_of}); limit is "
                         f"{dc['max_inventory_age_days']}. Re-export from SAP.")
        if age < 0:
            stops.append(f"Inventory snapshot date {as_of} is after the run date {run_date}")

    hist = defaultdict(dict)
    for r in sales:
        sku = r["SKU_ID"]
        try:
            monday = iso_week_monday(r["Week"])
            units = float(r["Units_Sold"])
        except ValueError:
            stops.append(f"Unreadable sales row: {r}")
            continue
        if units < 0:
            sku_issues[sku].append(f"Negative sales in {r['Week']} ({units:g}) - returns netted?")
        if monday in hist[sku]:
            stops.append(f"Duplicate sales row for {sku} {r['Week']}")
        hist[sku][monday] = units

    if hist and as_of is not None:
        last_week = max(max(h) for h in hist.values())
        missing = (iso_week_monday_of(as_of) - last_week).days // 7 - 1
        if missing > dc["max_missing_weeks_before_snapshot"]:
            stops.append(f"Sales history ends week of {last_week}, {missing} full week(s) before the "
                         f"inventory snapshot. Sales export is stale.")

    for sku in master_ids:
        if sku not in inv:
            sku_issues[sku].append("No inventory row in export")
        h = hist.get(sku, {})
        if not h:
            sku_issues[sku].append("No sales history (new launch?)")
            continue
        weeks = sorted(h)
        expected = (weeks[-1] - weeks[0]).days // 7 + 1
        if expected != len(weeks):
            sku_issues[sku].append(f"{expected - len(weeks)} missing week(s) in sales history")
        if len(weeks) < dc["min_history_weeks"]:
            sku_issues[sku].append(f"Only {len(weeks)} weeks of history (new launch?)")
        if sum(h[w] for w in weeks[-4:]) == 0:
            sku_issues[sku].append("Zero sales in last 4 weeks (delisted or data gap?)")
    for sku in set(inv) | set(hist):
        if sku not in master_ids:
            stops.append(f"{sku} appears in exports but not in SKU master")

    clean = {"inventory": inv, "history": hist, "as_of": as_of}
    return stops, dict(sku_issues), clean


def iso_week_monday_of(d):
    return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------- forecast

class Forecast:
    """Weekly forward forecast = flat base x festival factor for that week's month."""

    def __init__(self, base, start_monday, cfg, uplift=True):
        self.base = base
        self.start = start_monday
        fc = cfg["forecast"]
        self.months = set(fc["festival_months"])
        self.uplift = fc["festival_uplift"] if uplift else 0.0

    def week(self, i):
        thursday = self.start + timedelta(days=7 * i + 3)
        return self.base * (1 + self.uplift if thursday.month in self.months else 1)

    def demand(self, a, b):
        """Units demanded between week offsets a and b (fractional allowed)."""
        total, p = 0.0, a
        while p < b - 1e-9:
            i = math.floor(p)
            step = min(i + 1, b) - p
            total += self.week(i) * step
            p += step
        return total

    def cover(self, stock, offset=0.0, horizon=104):
        """Weeks the given stock lasts, starting at week offset."""
        p = offset
        while p < offset + horizon:
            i = math.floor(p)
            rem = i + 1 - p
            need = self.week(i) * rem
            if need <= 0:
                return horizon
            if stock < need:
                return p - offset + stock / self.week(i)
            stock -= need
            p = i + 1
        return horizon


def order_up_to(fc, on_hand, lead_time, target_weeks, multiple):
    """Quantity that brings cover back to target_weeks when the order lands.

    Demand during lead time that stock can't meet is lost, not back-ordered."""
    left_at_arrival = max(0.0, on_hand - fc.demand(0, lead_time))
    need = fc.demand(lead_time, lead_time + target_weeks) - left_at_arrival
    if need <= 0:
        return 0, left_at_arrival
    return int(math.ceil(need / multiple) * multiple), left_at_arrival


def zone(cover, pol):
    if cover < pol["min_weeks"]:
        return "below_min"
    if cover > pol["max_weeks"]:
        return "above_max"
    return "ok"


# ---------------------------------------------------------------- segmentation

def segment(master, hist, cfg):
    sc = cfg["segmentation"]
    n = cfg["forecast"]["baseline_weeks"]
    vol, cv = {}, {}
    for r in master:
        h = hist.get(r["SKU_ID"], {})
        q = [h[w] for w in sorted(h)][-n:]
        vol[r["SKU_ID"]] = sum(q)
        m = statistics.mean(q) if q else 0
        cv[r["SKU_ID"]] = statistics.pstdev(q) / m if len(q) > 1 and m else float("inf")
    total = sum(vol.values()) or 1
    seg, cum = {}, 0.0
    a_cut, b_cut = sc["abc_cutoffs"]
    x_cut, y_cut = sc["xyz_cv_cutoffs"]
    for sku in sorted(vol, key=vol.get, reverse=True):
        share_before = cum
        cum += vol[sku] / total
        abc = "A" if share_before < a_cut else "B" if share_before < b_cut else "C"
        xyz = "X" if cv[sku] <= x_cut else "Y" if cv[sku] <= y_cut else "Z"
        seg[sku] = (abc, xyz, cv[sku])
    return seg


# ---------------------------------------------------------------- rules

def lead_time_for(dist, cfg):
    lt = cfg["lead_time_weeks"].get(dist)
    return (lt, False) if lt is not None else (cfg["lead_time_weeks"]["default"], True)


def as_written(on_hand, a12, a4, std_qty, perishable, cfg, run_month):
    """Raghav's documented rules, applied literally. Used for the parallel-run comparison."""
    pol = cfg["policy"]["perishable" if perishable else "standard"]
    fest = run_month in cfg["forecast"]["festival_months"]
    avg = a12 * (1 + cfg["forecast"]["festival_uplift"]) if fest else a12
    cover = on_hand / avg if avg else float("inf")
    flags = []
    if a4 > a12 * (1 + cfg["policy"]["high_demand_trend"]):
        flags.append("HIGH_DEMAND")
    if cover < pol["min_weeks"]:
        flags.append("STOCKOUT_RISK")
    if cover > pol["max_weeks"]:
        flags.append("OVERSTOCK")
    if "HIGH_DEMAND" in flags:
        action, qty = "ORDER", std_qty * cfg["policy"]["high_demand_multiplier_as_written"]
    elif "STOCKOUT_RISK" in flags:
        action, qty = "ORDER", std_qty
    elif "OVERSTOCK" in flags:
        action, qty = "PAUSE", 0
    else:
        action, qty = "NONE", 0
    return {
        "aw_cover": round(cover, 1), "aw_flags": "+".join(flags) or "OK",
        "aw_action": action, "aw_qty": int(qty),
        "aw_cover_after": round((on_hand + qty) / avg, 1) if avg else None,
    }


def evaluate(sku_row, clean, sku_issues, seg, cfg):
    sku = sku_row["SKU_ID"]
    perishable = sku_row["Perishability"].strip().lower() == "high"
    pol = cfg["policy"]["perishable" if perishable else "standard"]
    p = cfg["policy"]
    fc_cfg = cfg["forecast"]
    as_of = clean["as_of"]
    start = iso_week_monday_of(as_of)
    abc, xyz, cv = seg.get(sku, ("C", "Z", float("inf")))
    lt, lt_assumed = lead_time_for(sku_row["Distributor_ID"], cfg)

    rec = {
        "sku": sku, "name": sku_row["SKU_Name"], "category": sku_row.get("Category", ""),
        "perishable": perishable, "vendor": sku_row["Distributor_ID"],
        "segment": abc + xyz, "cv": round(cv, 3) if cv != float("inf") else None,
        "lead_time_weeks": lt, "lead_time_assumed": lt_assumed,
        "min_weeks": pol["min_weeks"], "max_weeks": pol["max_weeks"],
        "standard_qty": int(sku_row["Standard_Reorder_Qty"]),
        "flags": [], "reasons": [], "action": "NONE", "suggested_qty": 0, "alt_qty": None,
    }

    issues = sku_issues.get(sku, [])
    h = clean["history"].get(sku, {})
    on_hand = clean["inventory"].get(sku)
    q = [h[w] for w in sorted(h)]
    if issues or on_hand is None or len(q) < fc_cfg["baseline_weeks"]:
        rec.update(flags=["DATA_ISSUE"], reasons=issues or ["Insufficient data"],
                   action="HOLD", suggested_qty=None, route="BLOCKED", on_hand=on_hand)
        return rec

    # Rule 1: baseline and trend, on raw history (uplift is never applied here).
    a12 = statistics.mean(q[-fc_cfg["baseline_weeks"]:])
    a4 = statistics.mean(q[-fc_cfg["trend_weeks"]:])
    trend = a4 / a12 - 1 if a12 else 0.0
    fc = Forecast(a12, start, cfg)
    fc_raw = Forecast(a12, start, cfg, uplift=False)
    cover = fc.cover(on_hand)
    cover_raw = fc_raw.cover(on_hand)
    sigma = statistics.stdev(q[-fc_cfg["baseline_weeks"]:])
    rec.update(
        on_hand=on_hand, avg_12w=round(a12, 1), avg_4w=round(a4, 1), trend_pct=round(trend * 100, 1),
        fcst_next_week=round(fc.week(0), 1), fcst_6w=round(fc.demand(0, 6)),
        cover_weeks=round(cover, 1), cover_no_uplift=round(cover_raw, 1),
        safety_stock=int(round(p["safety_stock_z"] * sigma * math.sqrt(lt))),
        lead_time_demand=int(round(fc.demand(0, lt))),
    )

    target = pol["target_weeks"]
    shelf = cfg["shelf_life_weeks"].get(sku) if perishable else None
    if shelf:
        target = min(target, shelf)
        if cover > shelf:
            rec["flags"].append("SHELF_LIFE_RISK")
            rec["reasons"].append(f"{cover:.1f} wks of stock vs {shelf} wk shelf life")

    qty, left = order_up_to(fc, on_hand, lt, target, p["order_multiple"])
    z = zone(cover, pol)
    buf = p["threshold_buffer_pct"]
    near_min = abs(cover - pol["min_weeks"]) <= pol["min_weeks"] * buf
    near_max = abs(cover - pol["max_weeks"]) <= pol["max_weeks"] * buf

    # Rule 2: stockout risk -> order up to target (fixes gap 1: fixed qty doesn't close the gap).
    if z == "below_min":
        rec["flags"].append("STOCKOUT_RISK")
        rec["action"], rec["suggested_qty"] = "ORDER", qty
        rec["reasons"].append(f"{cover:.1f} wks cover < {pol['min_weeks']} min; order-up-to {target} wks "
                              f"after {lt}-wk lead time")
        if cover < lt:
            rec["flags"].append("EXPEDITE")
            rec["reasons"].append(f"Runs out in {cover:.1f} wks, before a {lt}-wk lead time")
    # Rule 3: overstock -> pause, unless inside the buffer (gap 2).
    elif z == "above_max":
        rec["flags"].append("OVERSTOCK")
        if near_max:
            rec["flags"].append("BORDERLINE")
            rec["action"] = "ORDER" if qty else "NONE"
            rec["suggested_qty"] = qty
            rec["reasons"].append(f"{cover:.1f} wks is within {buf:.0%} of the {pol['max_weeks']}-wk max: "
                                  f"not pausing; top-up to {target} wks instead")
        else:
            rec["action"] = "PAUSE"
            rec["reasons"].append(f"{cover:.1f} wks cover > {pol['max_weeks']} max; pause next order")
    elif near_min or near_max:
        rec["flags"].append("BORDERLINE")
        edge = pol["min_weeks"] if near_min else pol["max_weeks"]
        rec["reasons"].append(f"{cover:.1f} wks is within {buf:.0%} of the {edge}-wk threshold")

    # Rule 4: high demand never auto-orders; show the trend-based quantity as an alternative.
    if trend > p["high_demand_trend"]:
        rec["flags"].append("HIGH_DEMAND")
        # The 4-week average already contains the recent lift, so no festival uplift on top.
        fc_trend = Forecast(a4, start, cfg, uplift=False)
        alt, _ = order_up_to(fc_trend, on_hand, lt, target, p["order_multiple"])
        rec["alt_qty"] = alt
        rec["reasons"].append(f"Last 4 wks +{trend:.0%} vs 12-wk avg. Real or one-off? "
                              f"If real, order {alt} instead of {rec['suggested_qty']}")
        if rec["action"] == "PAUSE":
            rec["flags"].append("CONFLICT")
            rec["reasons"].append("Overstocked but demand rising: decide pause vs keep ordering")

    # Rule 5: would the flag flip without the festival uplift? (gap 3)
    z_raw = zone(cover_raw, pol)
    if z_raw != z:
        rec["flags"].append("ASSUMPTION_SENSITIVE")
        rec["reasons"].append(f"Without festival uplift cover is {cover_raw:.1f} wks ({z_raw.replace('_', ' ')}), "
                              f"with it {cover:.1f} ({z.replace('_', ' ')})")

    # Rule 6: volatile SKUs always go to a human.
    if xyz == "Z":
        rec["flags"].append("VOLATILE")
        rec["reasons"].append(f"Demand CV {cv:.2f}: too erratic for rules")

    # Routing.
    review = REVIEW_FLAGS & set(rec["flags"])
    if rec["action"] == "NONE" and not review:
        rec["route"] = "PASS"
    elif (not review and not perishable and rec["action"] in ("ORDER", "PAUSE")
          and rec["segment"] in cfg["routing"]["auto_approve_segments"]):
        rec["route"] = "AUTO"
    else:
        rec["route"] = "REVIEW"
    if rec["action"] == "ORDER":
        rec["cover_after_order"] = round(fc.cover(left + rec["suggested_qty"], offset=lt), 1)
    return rec


# ---------------------------------------------------------------- KPIs

def kpi_baseline(clean, recs, cfg):
    """Backtest the 12-week average as a forecast over the weeks we can test."""
    n = cfg["forecast"]["baseline_weeks"]
    abs_err = err = actual = 0.0
    tested = 0
    for sku, h in clean["history"].items():
        q = [h[w] for w in sorted(h)]
        for t in range(n, len(q)):
            f = statistics.mean(q[t - n:t])
            abs_err += abs(f - q[t])
            err += f - q[t]
            actual += q[t]
            tested += 1
    scored = [r for r in recs if r.get("cover_weeks") is not None]
    return {
        "forecast_method": f"{n}-week moving average, 1 week ahead",
        "backtest_points": tested,
        "wape_pct": round(100 * abs_err / actual, 1) if actual else None,
        "bias_pct": round(100 * err / actual, 1) if actual else None,
        "skus_below_min_cover": sum(1 for r in scored if "STOCKOUT_RISK" in r["flags"]),
        "skus_above_max_cover": sum(1 for r in scored if "OVERSTOCK" in r["flags"]),
        "median_weeks_of_cover": round(statistics.median(r["cover_weeks"] for r in scored), 1) if scored else None,
        "share_routed_to_review_pct": round(100 * sum(r["route"] != "PASS" for r in recs) / len(recs), 1),
        "not_in_export_yet": ["fill rate", "actual stockout events", "write-off value",
                              "on-order quantities", "supplier lead times", "unit prices"],
    }


# ---------------------------------------------------------------- run

def run(data_dir, cfg, run_date=None):
    return run_rows(*load_inputs(data_dir), cfg, run_date)


def run_rows(master, inventory, sales, cfg, run_date=None):
    run_date = run_date or date.today()
    stops, sku_issues, clean = check_data(master, inventory, sales, cfg, run_date)
    meta = {
        "run_date": str(run_date), "inventory_as_of": str(clean["as_of"]),
        "created": datetime.now().isoformat(timespec="seconds"),
        "stops": stops, "sku_issues": sku_issues, "warnings": [],
    }
    if stops:
        return meta, []
    if any(v is None for k, v in cfg["lead_time_weeks"].items() if not k.startswith("_")):
        meta["warnings"].append(
            f"Supplier lead times not confirmed: using {cfg['lead_time_weeks']['default']} wk default. "
            "Order quantities and EXPEDITE flags depend on this.")
    seg = segment(master, clean["history"], cfg)
    recs = [evaluate(r, clean, sku_issues, seg, cfg) for r in master]
    month = clean["as_of"].month
    for r, m in zip(recs, master):
        if r.get("avg_12w") is not None:
            r.update(as_written(r["on_hand"], r["avg_12w"], r["avg_4w"], r["standard_qty"],
                                r["perishable"], cfg, month))
    meta["kpi"] = kpi_baseline(clean, recs, cfg)
    return meta, recs
