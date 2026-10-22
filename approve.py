"""Approval screen for the review queue.

    python3 approve.py              # latest run, http://localhost:8765
    python3 approve.py --run 2026-10-22_101500

Every decision is appended to outputs/decisions_log.csv (never edited in place; the
latest row per run+SKU wins). "Create Zoho drafts" writes outputs/<run>/zoho_po_drafts.csv
for the Zoho Inventory purchase-order import, status Draft.
"""
import argparse
import csv
import json
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "outputs"
LOG = OUT / "decisions_log.csv"
LOG_COLS = ["run_id", "decided_at", "reviewer", "sku", "route", "flags", "system_action", "system_qty",
            "alt_qty", "decision", "final_qty", "reason_code", "note", "on_hand", "avg_12w", "cover_weeks"]
ZOHO_COLS = ["Purchase Order Date", "Purchase Order Number", "Vendor Name", "Expected Delivery Date",
             "Item Name", "SKU", "Quantity", "Status", "Notes"]


def load_run(run_id):
    return json.loads((OUT / run_id / "run.json").read_text())


def decisions_for(run_id):
    if not LOG.exists():
        return {}
    latest = {}
    with open(LOG, newline="") as f:
        for row in csv.DictReader(f):
            if row["run_id"] == run_id:
                latest[row["sku"]] = row
    return latest


def record_decision(run_id, recs, body, reason_codes):
    row = validate_decision(run_id, recs, body, reason_codes)
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS)
        if new:
            w.writeheader()
        w.writerow(row)
    return row


def validate_decision(run_id, recs, body, reason_codes):
    """Checks one decision from the approval screen and returns the log row."""
    rec = next((r for r in recs if r["sku"] == body.get("sku")), None)
    if rec is None:
        raise ValueError("Unknown SKU")
    decision = body.get("decision")
    if decision not in ("APPROVE", "OVERRIDE", "REJECT"):
        raise ValueError("decision must be APPROVE, OVERRIDE or REJECT")
    final_qty = 0 if decision == "REJECT" else int(body.get("final_qty") or 0)
    if final_qty < 0:
        raise ValueError("Quantity cannot be negative")
    system_qty = rec["suggested_qty"] or 0
    if decision == "APPROVE" and final_qty != system_qty:
        decision = "OVERRIDE"
    reason = body.get("reason_code", "")
    if decision != "APPROVE" and reason not in reason_codes:
        raise ValueError("Overrides and rejections need a reason code")
    if rec["route"] == "BLOCKED" and decision == "APPROVE":
        raise ValueError("Blocked SKUs have no system quantity: enter one as an override")
    row = {
        "run_id": run_id, "decided_at": datetime.now().isoformat(timespec="seconds"),
        "reviewer": (body.get("reviewer") or "").strip() or "unknown", "sku": rec["sku"],
        "route": rec["route"], "flags": "+".join(rec["flags"]), "system_action": rec["action"],
        "system_qty": system_qty, "alt_qty": rec.get("alt_qty") or "", "decision": decision,
        "final_qty": final_qty, "reason_code": reason if decision != "APPROVE" else "",
        "note": (body.get("note") or "").strip(), "on_hand": rec.get("on_hand"),
        "avg_12w": rec.get("avg_12w"), "cover_weeks": rec.get("cover_weeks"),
    }
    return row


def build_zoho(run_id, data):
    lines, pending = zoho_lines(run_id, data, decisions_for(run_id))
    path = OUT / run_id / "zoho_po_drafts.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ZOHO_COLS)
        w.writeheader()
        w.writerows(lines)
    return {"path": str(path.relative_to(ROOT)), "lines": lines, "pending": pending,
            "pos": len({x["Purchase Order Number"] for x in lines})}


def zoho_lines(run_id, data, decided):
    """Draft PO lines from auto-approved SKUs and the latest decision per reviewed SKU."""
    recs, meta = data["recs"], data["meta"]
    lines, pending = [], []
    po_date = date.fromisoformat(meta["run_date"])
    for r in recs:
        if r["route"] == "AUTO":
            qty, note = r["suggested_qty"], "Auto-approved by rules"
        elif r["route"] in ("REVIEW", "BLOCKED"):
            d = decided.get(r["sku"])
            if d is None:
                pending.append(r["sku"])
                continue
            qty = int(d["final_qty"])
            note = f"{d['decision']} by {d['reviewer']}" + (f" ({d['reason_code']})" if d["reason_code"] else "")
        else:
            continue
        if qty > 0:
            eta = po_date + timedelta(weeks=r["lead_time_weeks"])
            lines.append({
                "Purchase Order Date": str(po_date),
                "Purchase Order Number": f"DRAFT-{run_id}-{r['vendor']}",
                "Vendor Name": r["vendor"], "Expected Delivery Date": str(eta),
                "Item Name": r["name"], "SKU": r["sku"], "Quantity": qty, "Status": "Draft",
                "Notes": note + (" | lead time ASSUMED" if r["lead_time_assumed"] else ""),
            })
    lines.sort(key=lambda x: (x["Vendor Name"], x["SKU"]))
    return lines, pending


class Handler(BaseHTTPRequestHandler):
    run_id = None
    cfg = None

    def send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/":
            return self.send(200, (ROOT / "approve.html").read_text(), "text/html")
        if self.path == "/api/run":
            data = load_run(self.run_id)
            return self.send(200, {**data, "decisions": decisions_for(self.run_id),
                                   "reason_codes": self.cfg["reason_codes"]})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            data = load_run(self.run_id)
            if self.path == "/api/decision":
                return self.send(200, record_decision(self.run_id, data["recs"], body, self.cfg["reason_codes"]))
            if self.path == "/api/zoho":
                return self.send(200, build_zoho(self.run_id, data))
            self.send(404, {"error": "not found"})
        except (ValueError, KeyError) as e:
            self.send(400, {"error": str(e)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="run id (default: latest)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    run_id = args.run or (OUT / "latest.txt").read_text().strip()
    data = load_run(run_id)
    if data["meta"]["stops"]:
        raise SystemExit(f"Run {run_id} was stopped by data checks; nothing to approve.")
    Handler.run_id = run_id
    Handler.cfg = json.loads((ROOT / "config.json").read_text())
    url = f"http://localhost:{args.port}"
    print(f"Review queue for run {run_id}: {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
