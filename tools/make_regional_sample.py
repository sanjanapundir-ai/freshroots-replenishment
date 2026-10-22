"""Builds data_mh_goa/: the 15 case SKUs plus 14 SAMPLE Maharashtrian and Goan lines.

SKU016-SKU029 are made up for demonstration (seeded, so reruns give the same files).
They are not Freshroots data. Patterns follow the real calendar:
Ganeshotsav (Ganesh Chaturthi 14 Sep 2026, ISO week 38), Diwali faral buying from
mid-October (Diwali 8 Nov 2026), Goa tourist season from October, kokum drinks fading after summer.

    python3 tools/make_regional_sample.py
"""
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "data", ROOT / "data_mh_goa"
WEEKS = list(range(27, 43))          # 2026-W27 .. W42, same window as the case export
AS_OF = "2026-10-19"
rng = random.Random(2026)

# id, name, category, perishability, std qty, supplier, region, base units/wk, pattern, units on hand
SKUS = [
    ("SKU016", "Freshroots Kanda Poha 500g", "Staple", "Low", 400, "DIST005", "Maharashtra", 180, "flat", 1500),
    ("SKU017", "Freshroots Bhajani Chakli 200g", "Snack", "Low", 300, "DIST005", "Maharashtra", 90, "diwali", 420),
    ("SKU018", "Freshroots Pune Bhakarwadi 250g", "Snack", "Low", 250, "DIST005", "Maharashtra", 70, "diwali_soft", 600),
    ("SKU019", "Freshroots Kokum Sharbat 750ml", "Beverage", "Low", 200, "DIST005", "Maharashtra", 60, "fading", 1150),
    ("SKU020", "Freshroots Kolhapuri Gul (Jaggery) 1kg", "Staple", "Low", 300, "DIST005", "Maharashtra", 120, "flat", 1100),
    ("SKU021", "Freshroots Thalipeeth Bhajani 500g", "Staple", "Low", 150, "DIST005", "Maharashtra", 45, "flat", 380),
    ("SKU022", "Freshroots Ukadiche Modak Rice Flour 500g", "Staple", "Low", 200, "DIST005", "Maharashtra", 40, "ganesh", 900),
    ("SKU023", "Freshroots Shrewsbury Butter Biscuits 200g", "Snack", "Low", 250, "DIST005", "Maharashtra", 85, "diwali_soft", 640),
    ("SKU024", "Freshroots Goan Cashews W320 250g", "Snack", "Low", 200, "DIST006", "Goa", 55, "tourist", 300),
    ("SKU025", "Freshroots Goan Bebinca 400g", "Snack", "High", 120, "DIST006", "Goa", 30, "flat", 100),
    ("SKU026", "Freshroots Goan Ukda Red Rice 5kg", "Staple", "Low", 100, "DIST006", "Goa", 35, "flat", 330),
    ("SKU027", "Freshroots Recheado Masala 100g", "Condiment", "Low", 150, "DIST006", "Goa", 40, "tourist_soft", 300),
    ("SKU028", "Freshroots Sol Kadhi 500ml", "Beverage", "High", 200, "DIST006", "Goa", 65, "fading", 290),
    ("SKU029", "Freshroots Puran Poli Ready Mix 400g", "Staple", "Low", 150, "DIST005", "Maharashtra", 50, "launch", 260),
]


def factor(pattern, wk):
    if pattern == "diwali":
        return 1.0 + {40: 0.25, 41: 0.45, 42: 0.6}.get(wk, 0)
    if pattern == "diwali_soft":
        return 1.0 + {41: 0.12, 42: 0.18}.get(wk, 0)
    if pattern == "ganesh":
        return 1.0 + {36: 0.8, 37: 2.0, 38: 2.6, 39: 0.3}.get(wk, 0)
    if pattern == "fading":
        return max(0.55, 1.15 - 0.035 * (wk - 27))
    if pattern == "tourist":
        return 1.0 + max(0, wk - 38) * 0.08
    if pattern == "tourist_soft":
        return 1.0 + max(0, wk - 39) * 0.04
    return 1.0


def main():
    OUT.mkdir(exist_ok=True)
    with open(SRC / "sku_master.csv") as f:
        master = list(csv.DictReader(f))
    for r in master:
        r["Region"] = "Maharashtra & Goa"
    for s in SKUS:
        master.append({"SKU_ID": s[0], "SKU_Name": s[1], "Category": s[2], "Perishability": s[3],
                       "Standard_Reorder_Qty": s[4], "Unit_of_Measure": "Units", "Distributor_ID": s[5], "Region": s[6]})
    with open(OUT / "sku_master.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(master[0]))
        w.writeheader()
        w.writerows(master)

    with open(SRC / "current_inventory.csv") as f:
        inv = list(csv.DictReader(f))
    loc = {"DIST005": "Pune Central Warehouse", "DIST006": "Verna (Goa) Depot"}
    inv += [{"SKU_ID": s[0], "Location": loc[s[5]], "Units_On_Hand": s[9], "As_Of_Date": AS_OF} for s in SKUS]
    with open(OUT / "current_inventory.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(inv[0]))
        w.writeheader()
        w.writerows(inv)

    with open(SRC / "weekly_sales.csv") as f:
        sales = list(csv.DictReader(f))
    for s in SKUS:
        weeks = range(36, 43) if s[8] == "launch" else WEEKS     # new launch: 7 weeks of history only
        for wk in weeks:
            units = s[7] * factor(s[8], wk) * rng.uniform(0.95, 1.05)
            sales.append({"SKU_ID": s[0], "Week": f"2026-W{wk}", "Units_Sold": int(round(units))})
    with open(OUT / "weekly_sales.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["SKU_ID", "Week", "Units_Sold"])
        w.writeheader()
        w.writerows(sales)
    print(f"{len(master)} SKUs -> {OUT}")


if __name__ == "__main__":
    main()
