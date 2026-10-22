"""Builds data_sample_ops/: SAMPLE data for the parts of Freshroots that have no real data yet.

Everything here is made up (seeded, so reruns give the same files) to show what the dashboard
looks like after a 6-week pilot, weeks 37-42 of 2026 (7 Sep - 18 Oct). It follows the case:

- 60 distributors across Maharashtra and Goa, about 18-25 lakh a year each
- the 28-lakh Nashik account cuts orders 30% after missing a scheme notice (from week 33)
- a competitor scheme hits Nashik, Kolhapur and Aurangabad distributors from week 41
- 50-80 WhatsApp queries a day for 4 CS reps, most routine; Rohan on leave in week 39
- a 22-lakh raw material PO held at the PO gate after the order-drop alerts
- stockouts cost about 18-22 lakh a quarter in lost sales, perishable write-offs 10-12 lakh

    python3 tools/make_sample_ops.py
"""
import csv
import math
import random
import statistics
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ops import CATEGORIES, IST, add_working_hours  # noqa: E402

OUT = ROOT / "data_sample_ops"
rng = random.Random(4242)
PILOT_START, PILOT_END = date(2026, 9, 7), date(2026, 10, 18)
NOW = datetime(2026, 10, 22, 11, 0, tzinfo=IST)         # the moment the sample is "as of"
WEEKS = list(range(27, 43))


def write(name, rows, cols=None):
    cols = cols or list(rows[0])
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def week_monday(wk):
    return date.fromisocalendar(2026, wk, 1)


def stamp(dt):
    return dt.astimezone(IST).strftime("%Y-%m-%d %H:%M") if dt else ""


# ---------------------------------------------------------------- prices (trade price per unit, INR)
PRICES = {"SKU001": 20, "SKU002": 45, "SKU003": 140, "SKU004": 175, "SKU005": 120, "SKU006": 260, "SKU007": 60,
          "SKU008": 35, "SKU009": 210, "SKU010": 220, "SKU011": 55, "SKU012": 160, "SKU013": 190, "SKU014": 120,
          "SKU015": 320, "SKU016": 45, "SKU017": 60, "SKU018": 90, "SKU019": 180, "SKU020": 90, "SKU021": 85,
          "SKU022": 70, "SKU023": 160, "SKU024": 450, "SKU025": 350, "SKU026": 400, "SKU027": 90, "SKU028": 120,
          "SKU029": 110}

# ---------------------------------------------------------------- distributors
TOWNS = [("Pune", "Maharashtra", "Pune"), ("Mumbai", "Maharashtra", "Mumbai"), ("Thane", "Maharashtra", "Mumbai"),
         ("Nashik", "Maharashtra", "North Maharashtra"), ("Aurangabad", "Maharashtra", "Marathwada"),
         ("Kolhapur", "Maharashtra", "South Maharashtra"), ("Nagpur", "Maharashtra", "Vidarbha"),
         ("Solapur", "Maharashtra", "South Maharashtra"), ("Satara", "Maharashtra", "South Maharashtra"),
         ("Jalgaon", "Maharashtra", "North Maharashtra"), ("Ratnagiri", "Maharashtra", "Konkan"),
         ("Amravati", "Maharashtra", "Vidarbha"), ("Latur", "Maharashtra", "Marathwada"),
         ("Panaji", "Goa", "Goa"), ("Margao", "Goa", "Goa"), ("Mapusa", "Goa", "Goa"), ("Ponda", "Goa", "Goa")]
FIRST = ["Shree Ganesh", "Sai", "Om", "Mahalaxmi", "Navratna", "Siddhivinayak", "Jai Bhavani", "Vitthal", "Kamat",
         "Naik", "Patil", "Deshmukh", "Joshi", "Sawant", "Kulkarni", "Shinde", "Pai", "Gaonkar", "Parab", "Desai"]
LAST = ["Traders", "Distributors", "Agencies", "Enterprises", "Marketing", "Sales Corporation"]
REGION_CS = {"Mumbai": "Farah", "Pune": "Sunita", "North Maharashtra": "Rohan", "Marathwada": "Rohan",
             "South Maharashtra": "Sunita", "Vidarbha": "Kiran", "Konkan": "Kiran", "Goa": "Farah"}
REGION_RSM = {"Mumbai": "RSM Mumbai", "Pune": "RSM Pune", "North Maharashtra": "RSM North", "Marathwada": "RSM North",
              "South Maharashtra": "RSM South", "Vidarbha": "RSM Vidarbha", "Konkan": "RSM South", "Goa": "RSM Goa"}
COMPETITOR_TOWNS = {"Nashik", "Kolhapur", "Aurangabad"}


def distributors():
    rows, used = [], set()
    weights = [9, 9, 5, 5, 4, 4, 4, 3, 2, 2, 2, 2, 2, 3, 2, 1, 1]
    for i in range(60):
        town, state, zone = rng.choices(TOWNS, weights)[0]
        if i == 0:
            town, state, zone = TOWNS[3]                      # D001 is the Nashik account from the case
        while True:
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}, {town}"
            if name not in used:
                used.add(name)
                break
        annual = 2_800_000 if i == 0 else int(rng.triangular(900_000, 3_200_000, 2_000_000) / 10_000) * 10_000
        rows.append({"distributor_id": f"D{i + 1:03d}", "distributor": name, "town": town, "state": state, "zone": zone,
                     "cs_rep": REGION_CS[zone], "sales_owner": REGION_RSM[zone], "annual_value_inr": annual})
    rows.sort(key=lambda r: -r["annual_value_inr"])
    for rank, r in enumerate(rows, 1):
        r["rank"] = rank
        r["top50"] = rank <= 50
    return rows


def orders(dists):
    rows = []
    for d in dists:
        weekly = d["annual_value_inr"] / 52
        for wk in WEEKS:
            f = 1.0 + (0.18 if wk >= 40 else 0) + rng.uniform(-0.07, 0.07)   # festival lift from October
            if d["distributor_id"] == "D001" and wk >= 33:
                f *= 0.70                                                    # missed scheme: 30% cut
            if d["town"] in COMPETITOR_TOWNS and wk >= 41:
                f *= rng.uniform(0.58, 0.75)                                 # competitor scheme
            rows.append({"distributor_id": d["distributor_id"], "distributor": d["distributor"], "zone": d["zone"],
                         "state": d["state"], "week": f"2026-W{wk}", "week_start": str(week_monday(wk)),
                         "order_value_inr": int(round(weekly * f, -2))})
    return rows


# ---------------------------------------------------------------- distributor queries
CAT_W = {"Order status": 28, "Delivery ETA": 18, "Scheme eligibility": 12, "Returns or credit note": 9,
         "Invoice or pricing": 13, "Complaint": 8, "Other": 12}
ASKS = {
    "Order status": ["Where is order {o}? Placed {d}.", "Order {o} shows dispatched, not received", "Is order {o} confirmed?"],
    "Delivery ETA": ["When will the {s} cases reach?", "Truck expected today?", "ETA for {s} restock before Diwali?"],
    "Scheme eligibility": ["Am I eligible for the Diwali scheme?", "Scheme slab for {s}: what is the target?", "Did my registration for the festive scheme go through?"],
    "Returns or credit note": ["Credit note for damaged {s} cases not received", "Return of expired {s}: pickup date?", "Status of credit note CN-{o}"],
    "Invoice or pricing": ["Invoice {o} rate differs from price list", "Need GST invoice copy for {o}", "New price list for {s}?"],
    "Complaint": ["Short supply of {s} in last order", "Leaking {s} pack, 2 cases", "Salesman did not visit this week"],
    "Other": ["Need new display stand", "Change of delivery address", "Want to add {s} to my range"],
}
RESOLVE = {
    "Order status": "Shared dispatch status from SAP", "Delivery ETA": "Gave ETA from logistics",
    "Scheme eligibility": "Confirmed eligibility and registered", "Returns or credit note": "Credit note raised / pickup booked",
    "Invoice or pricing": "Sent corrected invoice", "Complaint": "Replacement sent, apology call by RSM",
    "Other": "Passed to sales team",
}
SKU_WORDS = ["mango drink", "oats cookies", "almond milk", "poha", "chakli", "kokum sharbat", "coconut water", "cashews", "bread"]
REPS = ["Sunita", "Rohan", "Farah", "Kiran"]


def working_minutes(a, b):
    """Working minutes between a and b (Mon-Sat 9:00-19:00 IST)."""
    total, t = 0, a.astimezone(IST)
    while t < b:
        step = min(b, t + timedelta(minutes=15))
        if t.weekday() != 6 and time(9) <= t.time() < time(19):
            total += (step - t).total_seconds() / 60
        t = step
    return total


def add_working_minutes(start, minutes):
    return add_working_hours(start, minutes / 60)


def queries(dists):
    rows, qid = [], 1
    d = PILOT_START
    while d <= NOW.date():                      # the 6-week pilot plus this week so far
        wk = d.isocalendar()[1]
        base = {0: 74, 1: 62, 2: 60, 3: 58, 4: 61, 5: 44, 6: 10}[d.weekday()]
        n = int(base * (1.15 if wk >= 40 else 1.0) * rng.uniform(0.9, 1.1))
        for _ in range(n):
            hour = rng.choices(range(7, 23), [1, 3, 9, 10, 9, 6, 6, 7, 8, 8, 6, 4, 3, 2, 1, 1])[0]
            received = datetime.combine(d, time(hour, rng.randrange(60)), IST)
            if received > NOW:
                continue
            cat_w = dict(CAT_W)
            if wk == 40:
                cat_w["Scheme eligibility"] = 30                             # Diwali scheme launch week
            cat = rng.choices(list(cat_w), list(cat_w.values()))[0]
            dist = rng.choices(dists, [r["annual_value_inr"] for r in dists])[0]
            rep = dist["cs_rep"]
            reassigned = None
            if rep == "Rohan" and d in (date(2026, 9, 22), date(2026, 9, 23), date(2026, 9, 24), date(2026, 9, 25)):
                reassigned, rep = "Rohan", "Sunita"                          # leave handoff
            due = add_working_hours(received, 2)
            # minutes of working time to the first reply: most fast, Mondays and leave weeks slower
            med = 55 * (1.6 if d.weekday() == 0 else 1.0) * (1.5 if reassigned else 1.0) * (0.85 if wk >= 41 else 1.0)
            reply_wm = max(4, rng.lognormvariate(math.log(med), 0.75))
            first = add_working_minutes(received, reply_wm)
            res_wm = reply_wm + {"Complaint": rng.uniform(300, 1500), "Returns or credit note": rng.uniform(200, 900),
                                 "Invoice or pricing": rng.uniform(60, 500)}.get(cat, rng.uniform(5, 120))
            resolved = add_working_minutes(received, res_wm)
            status = "RESOLVED"
            if first > NOW:
                first, resolved, status = None, None, "OPEN"
            elif resolved > NOW:
                resolved, status = None, "RESPONDED"
            ask = rng.choice(ASKS[cat]).format(o=rng.randrange(4100, 9900), d=(d - timedelta(days=rng.randrange(1, 6))).strftime("%d %b"),
                                               s=rng.choice(SKU_WORDS))
            rows.append({
                "id": qid, "received_at": stamp(received), "reply_due": stamp(due), "distributor_id": dist["distributor_id"],
                "distributor": dist["distributor"], "region": dist["state"], "zone": dist["zone"],
                "channel": rng.choices(["WhatsApp", "Phone", "Field rep"], [86, 10, 4])[0], "category": cat, "summary": ask,
                "assigned_to": rep, "reassigned_from": reassigned or "", "status": status,
                "first_reply_at": stamp(first), "resolved_at": stamp(resolved),
                "reply_state": ("on time" if first <= due else "late") if first else ("overdue" if NOW > due else "waiting"),
                "reply_working_min": round(working_minutes(received, first)) if first else "",
                "routine": cat in ("Order status", "Delivery ETA", "Scheme eligibility", "Returns or credit note"),
                "resolution": RESOLVE[cat] if resolved else "", "week": f"2026-W{wk}", "hour": hour, "weekday": d.strftime("%a"),
            })
            qid += 1
        d += timedelta(days=1)
    return rows


# ---------------------------------------------------------------- weekly business KPIs (baseline the plan tracks)
def weekly_kpis():
    rows = []
    for wk in WEEKS:
        fest = wk >= 40
        stockouts = int(rng.uniform(7, 11) + (5 if fest else 0) + (3 if wk == 41 else 0))
        rows.append({
            "week": f"2026-W{wk}", "week_start": str(week_monday(wk)),
            "fill_rate_pct": round(rng.uniform(95.2, 96.8) - (2.6 if fest else 0) - (1.2 if wk == 41 else 0), 1),
            "stockout_incidents": stockouts,
            "lost_sales_inr": int(round(stockouts * rng.uniform(15000, 18500), -3)),
            "writeoff_inr": int(round(rng.uniform(70000, 98000) + (25000 if wk in (35, 36) else 0), -3)),
            "inventory_value_inr": int(round(rng.uniform(3.9e6, 4.3e6) + (3.5e5 if fest else 0), -4)),
            "forecast_wape_pct": round(rng.uniform(8.5, 11.5) + (2.5 if fest else 0), 1),
        })
    return rows


# ---------------------------------------------------------------- alerts (6-week pilot)
OWNER = {"dist_order_drop": "Regional Sales Manager", "sales_volume": "Head of Sales", "fulfilment": "Logistics Manager",
         "stockouts": "Demand Planner", "overstock": "Procurement Head", "complaints": "CS Team Lead",
         "cs_response": "CS Team Lead", "po_gate": "Procurement Head", "wape": "Demand Planner",
         "writeoffs": "Finance Controller", "credit": "Finance Controller", "scheme_uptake": "Head of Sales"}
DEADLINE = {"dist_order_drop": 24, "sales_volume": 72, "fulfilment": 48, "stockouts": 24, "overstock": 72,
            "complaints": 48, "cs_response": 24, "po_gate": 24, "wape": 120, "writeoffs": 120, "credit": 72, "scheme_uptake": 24}
METRIC = {"dist_order_drop": "Distributor order size (top 50)", "sales_volume": "Sales volume", "fulfilment": "Order fulfilment rate",
          "stockouts": "Stockout incidents", "overstock": "Overstock value", "complaints": "Distributor complaints",
          "cs_response": "CS first response time", "po_gate": "Raw material PO above 5 lakh", "wape": "Forecast error (WAPE)",
          "writeoffs": "Write-offs", "credit": "Distributor credit overdue", "scheme_uptake": "Scheme uptake"}


def alerts(dists, ords, qs, kpis):
    out = []

    def add(metric, raised, title, detail="", raised_by="Priya", ack_h=None, action="", res_h=None, resolution="", owner_name=""):
        due = raised + timedelta(hours=DEADLINE[metric])
        ack = raised + timedelta(hours=ack_h) if ack_h is not None else None
        res = raised + timedelta(hours=res_h) if res_h is not None else None
        if ack and ack > NOW:
            ack = res = None
        if res and res > NOW:
            res = None
        state = "RESOLVED" if res else "ACKNOWLEDGED" if ack else ("ESCALATED" if NOW > due else "OPEN")
        out.append({"id": len(out) + 1, "metric_id": metric, "metric": METRIC[metric], "title": title, "detail": detail,
                    "raised_by": raised_by, "raised_at": stamp(raised), "due_at": stamp(due), "owner_role": OWNER[metric],
                    "owner_name": owner_name or ("Raghav Kulkarni" if OWNER[metric] == "Demand Planner" else ""),
                    "escalate_to": "Deepa Nair", "state": state,
                    "hours_left": round((due - NOW).total_seconds() / 3600) if state in ("OPEN", "ESCALATED") else "",
                    "acknowledged_at": stamp(ack), "action_taken": action if ack else "",
                    "ack_hours": round((ack - raised).total_seconds() / 3600, 1) if ack else "",
                    "ack_timing": ("on time" if ack <= due else "late") if ack else "",
                    "resolved_at": stamp(res), "resolution": resolution if res else "", "week": f"2026-W{raised.isocalendar()[1]}"})

    def at(d, h, m=0):
        return datetime.combine(d, time(h, m), IST)

    # order drops: compare each top-50 distributor's week to its previous 4-week average
    by = {}
    for o in ords:
        by.setdefault(o["distributor_id"], []).append(o)
    names = {d["distributor_id"]: d for d in dists}
    for did, rows in by.items():
        if not names[did]["top50"]:
            continue
        rows.sort(key=lambda r: r["week"])
        for i in range(4, len(rows)):
            wk = int(rows[i]["week"][-2:])
            if wk < 37:
                continue
            avg4 = statistics.mean(r["order_value_inr"] for r in rows[i - 4:i])
            drop = 1 - rows[i]["order_value_inr"] / avg4
            if drop > 0.20:
                d = names[did]
                raised = at(week_monday(wk) + timedelta(days=7), 10)              # Monday after the week closes
                if raised > NOW:
                    continue
                competitor = d["town"] in COMPETITOR_TOWNS and wk >= 41
                hrs = rng.choice([3, 5, 8, 20, 30]) if not competitor else rng.choice([2, 4, 6])
                add("dist_order_drop", raised, f"{d['distributor']}: week {wk} orders {drop:.0%} below 4-week average",
                    f"Week {wk}: INR {rows[i]['order_value_inr']:,} vs 4-week average INR {avg4:,.0f}. Owner: {d['sales_owner']}",
                    ack_h=hrs, action="Called distributor: competitor scheme till 31 Oct, matching with our Diwali slab" if competitor
                    else "Called distributor: stock still full from last order, next order next week",
                    res_h=hrs + rng.uniform(20, 70), resolution="Orders back within 10% of average" if not competitor
                    else "Counter-scheme approved for the 3 markets", owner_name=d["sales_owner"])
    # the PO gate: the 22-lakh oats order held after the drop alerts; others routine
    add("po_gate", at(date(2026, 10, 20), 11), "Raw material PO 22 lakh: oats and millet flour",
        "Supplier: Agro Mills. Planned for Diwali volumes.", raised_by="Procurement", ack_h=6,
        action="Checked 48 h alerts: order drops in Nashik, Kolhapur, Aurangabad. Holding; cut to 15 lakh", res_h=26,
        resolution="Released at 15 lakh after Monday review")
    for d, amt, item in [(date(2026, 9, 9), "8.5", "packaging film"), (date(2026, 9, 23), "6.2", "mango pulp"),
                         (date(2026, 10, 7), "11", "cashew kernels"), (date(2026, 10, 21), "7.4", "kokum concentrate")]:
        late = item == "mango pulp"
        add("po_gate", at(d, 15), f"Raw material PO {amt} lakh: {item}", raised_by="Procurement",
            ack_h=31 if late else rng.choice([2, 4, 5]), action="Checked 48 h alerts: nothing relevant. Release",
            res_h=(33 if late else 8), resolution="Released")
    # stockouts from engine runs (Mon and Thu)
    d = PILOT_START
    while d <= date(2026, 10, 22):
        if d.weekday() in (0, 3) and rng.random() < 0.7:
            n = rng.randint(2, 7) + (2 if d >= date(2026, 10, 1) else 0)
            add("stockouts", at(d, 9, 40), f"{n} A-class SKUs at stockout risk in run {d}_0930", raised_by="Replenishment engine",
                ack_h=rng.choice([1, 2, 3, 6, 30]), action="Expedited the 2 lowest; rest ordered up to target",
                res_h=rng.uniform(30, 80), resolution="Cover back above minimum")
        d += timedelta(days=1)
    # CS first response: days where the median reply ran over 2 working hours
    days = {}
    for q in qs:
        if q["reply_working_min"] != "":
            days.setdefault(q["received_at"][:10], []).append(q["reply_working_min"])
    for day, mins in sorted(days.items()):
        if statistics.median(mins) > 120:
            dd = date.fromisoformat(day)
            add("cs_response", at(dd + timedelta(days=1), 9, 30), f"Median first reply {statistics.median(mins):.0f} min on {dd:%a %d %b}",
                raised_by="Priya", ack_h=rng.choice([2, 4, 26]), action="Moved two reps' queues; Monday backlog shift starts 8:30",
                res_h=48, resolution="Next day median under 90 min")
    # complaints, fulfilment, write-offs, credit, scheme, overstock, WAPE, sales
    for d, who in [(date(2026, 9, 17), "Kamat Agencies, Margao"), (date(2026, 10, 8), "Patil Traders, Satara"), (date(2026, 10, 19), "Sai Distributors, Pune")]:
        add("complaints", at(d, 12), f"3 complaints this week from {who}", "Short supply twice, one leaking pack", raised_by="CS Team Lead",
            ack_h=rng.choice([5, 9]), action="RSM visited; replacement and credit note", res_h=60, resolution="Distributor confirmed fixed")
    for k in kpis:
        wk = int(k["week"][-2:])
        if wk >= 37 and k["fill_rate_pct"] < 95:
            add("fulfilment", at(week_monday(wk) + timedelta(days=7), 10), f"Fill rate {k['fill_rate_pct']}% in week {wk}",
                raised_by="Priya", ack_h=rng.choice([6, 20, 52]), action="Pune depot short on chakli and almond milk; extra truck Thu",
                res_h=90, resolution="Week after back to 95%+")
        if wk >= 37 and k["writeoff_inr"] > 100000:
            add("writeoffs", at(week_monday(wk) + timedelta(days=8), 11), f"Perishable write-off INR {k['writeoff_inr']:,} in week {wk}",
                raised_by="Finance", ack_h=40, action="Almond milk batch expired at Nagpur; reduce cover to 3.5 wks", res_h=110,
                resolution="Shelf-life cap added for perishables")
    add("credit", at(date(2026, 9, 28), 10), "Navratna Distributors, Nagpur: 52 days overdue", raised_by="Finance",
        ack_h=20, action="Payment plan agreed: 3 instalments", res_h=200, resolution="First instalment received")
    add("credit", at(date(2026, 10, 19), 10), "Shree Ganesh Agencies, Jalgaon: 47 days overdue", raised_by="Finance")
    add("scheme_uptake", at(date(2026, 10, 5), 10), "Diwali scheme: 54% of eligible distributors registered", raised_by="Head of Sales",
        ack_h=3, action="Reps calling 41 unregistered distributors today", res_h=30, resolution="Registration at 81% at close")
    add("overstock", at(date(2026, 10, 1), 10), "Overstock at 128% of target: kokum sharbat, quinoa", raised_by="Priya",
        ack_h=10, action="Paused open POs for both SKUs", res_h=80, resolution="Next orders paused, stock running down")
    add("overstock", at(date(2026, 10, 21), 10), "Overstock at 124% of target: modak flour after Ganeshotsav", raised_by="Priya")
    add("wape", at(date(2026, 10, 1), 9), "September forecast error 13.9% on festival SKUs", raised_by="Priya",
        ack_h=50, action="Reviewed worst 10: Ganeshotsav lines under-forecast; per-SKU seasonality in phase 2", res_h=120, resolution="Noted for phase 2")
    add("sales_volume", at(date(2026, 10, 19), 10), "Week 42 sales 11% below last year in North Maharashtra", raised_by="Priya",
        ack_h=None)
    out.sort(key=lambda a: a["raised_at"])
    for i, a in enumerate(out, 1):
        a["id"] = i
    return out


# ---------------------------------------------------------------- Raghav's decisions over 12 runs
REASONS = ["TREND_REAL", "TREND_TEMPORARY", "COMPETITOR_SCHEME", "DISTRIBUTOR_SIGNAL", "PROMO_PLANNED", "SUPPLIER_CONSTRAINT", "SHELF_LIFE", "OTHER"]


def decisions():
    with open(ROOT / "outputs" / "2026-10-22_145516" / "recommendations.csv") as f:
        recs = list(csv.DictReader(f))
    flagged = [r for r in recs if r["route"] in ("REVIEW", "BLOCKED")]
    rows = []
    d = PILOT_START
    while d <= date(2026, 10, 19):
        if d.weekday() in (0, 3):
            run = f"{d}_0930"
            for r in rng.sample(flagged, k=min(len(flagged), rng.randint(8, 13))):
                sys_q = int(float(r["suggested_qty"] or 0)) if r["suggested_qty"] else 0
                sys_q = int(round(sys_q * rng.uniform(0.8, 1.2), -1)) if sys_q else (rng.choice([0, 0, 120, 200]) if r["route"] == "BLOCKED" else 0)
                truth = max(0, int(round((sys_q or 150) * rng.uniform(0.75, 1.3), -1)))
                if rng.random() < 0.27 or r["route"] == "BLOCKED":
                    reason = rng.choices(REASONS, [22, 12, 14, 12, 14, 8, 8, 10])[0]
                    good = {"TREND_REAL": 0.8, "COMPETITOR_SCHEME": 0.75, "PROMO_PLANNED": 0.8, "DISTRIBUTOR_SIGNAL": 0.7,
                            "SUPPLIER_CONSTRAINT": 0.6, "SHELF_LIFE": 0.7, "TREND_TEMPORARY": 0.55, "OTHER": 0.4}[reason]
                    final = int(round(truth + (truth - sys_q) * rng.uniform(-0.3, 0.2), -1)) if rng.random() < good \
                        else int(round(sys_q + (sys_q - truth) * rng.uniform(0.3, 0.8), -1))
                    final = max(0, final)
                    decision = "REJECT" if final == 0 and sys_q > 0 else "OVERRIDE"
                    if decision == "OVERRIDE" and final == sys_q:
                        final += 10
                else:
                    reason, final, decision = "", sys_q, "APPROVE"
                rows.append({"run_id": run, "decided_at": f"{d}T{rng.randint(10, 16):02d}:{rng.randrange(60):02d}:00",
                             "reviewer": "Raghav Kulkarni", "sku": r["sku"], "name": r["name"], "route": r["route"], "flags": r["flags"],
                             "system_action": r["action"], "system_qty": sys_q, "alt_qty": r["alt_qty"], "decision": decision,
                             "final_qty": final, "reason_code": reason, "note": "", "hindsight_qty": truth,
                             "system_error": abs(sys_q - truth), "final_error": abs(final - truth),
                             "override_helped": "" if decision == "APPROVE" else ("YES" if abs(final - truth) < abs(sys_q - truth) else "NO")})
        d += timedelta(days=1)
    return rows


def main():
    OUT.mkdir(exist_ok=True)
    dists = distributors()
    write("distributors.csv", dists)
    ords = orders(dists)
    write("distributor_orders.csv", ords)
    qs = queries(dists)
    write("dist_queries.csv", qs)
    kpis = weekly_kpis()
    write("weekly_kpis.csv", kpis)
    write("alerts.csv", alerts(dists, ords, qs, kpis))
    write("decisions.csv", decisions())
    write("sku_prices.csv", [{"sku": k, "trade_price_inr": v} for k, v in PRICES.items()])


if __name__ == "__main__":
    main()
