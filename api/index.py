"""Hosted API (Vercel Python function) over Neon Postgres.

    GET  /api/runs             recent runs
    GET  /api/run?id=<run_id>  one run with its latest decision per SKU (default: newest run)
    POST /api/run              {files: {sku_master.csv, current_inventory.csv, weekly_sales.csv}, as_of?}
    POST /api/decision         {run_id, sku, decision, final_qty, reason_code, note, reviewer}
    POST /api/zoho             {run_id} -> draft PO lines and CSV text
    GET  /api/decisions.csv    the whole decision log, for review.py

Needs DATABASE_URL. Same engine and validation as the local tools.
"""
import csv
import io
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

import engine  # noqa: E402
import ops  # noqa: E402
from approve import LOG_COLS, ZOHO_COLS, validate_decision, zoho_lines  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
with open(os.path.join(ROOT, "config.json")) as f:
    CFG = json.load(f)


def db():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, autocommit=True)


def to_json(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def latest_decisions(cur, run_id):
    cur.execute("SELECT DISTINCT ON (sku) * FROM decisions WHERE run_id = %s ORDER BY sku, id DESC", (run_id,))
    out = {}
    for r in cur.fetchall():
        r.pop("id")
        r["decided_at"] = r["decided_at"].astimezone(IST).isoformat(timespec="seconds")
        out[r["sku"]] = r
    return out


def load_run(cur, run_id):
    if run_id:
        cur.execute("SELECT run_id, data FROM runs WHERE run_id = %s", (run_id,))
    else:
        cur.execute("SELECT run_id, data FROM runs ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    if row is None:
        raise LookupError("No such run" if run_id else "No runs yet: upload an SAP export first")
    return row["run_id"], row["data"]


def list_runs(cur):
    cur.execute("""SELECT r.run_id, r.run_date, r.inventory_as_of, r.stopped, r.created_at,
                          jsonb_array_length(r.data->'recs') AS skus,
                          (SELECT count(*) FROM jsonb_array_elements(r.data->'recs') x
                            WHERE x->>'route' IN ('REVIEW', 'BLOCKED')) AS flagged,
                          (SELECT count(DISTINCT sku) FROM decisions d WHERE d.run_id = r.run_id) AS decided
                   FROM runs r ORDER BY r.created_at DESC LIMIT 50""")
    return cur.fetchall()


def create_run(cur, body):
    master, inventory, sales = engine.load_texts(body.get("files") or {})
    run_date = date.fromisoformat(body["as_of"]) if body.get("as_of") else datetime.now(IST).date()
    meta, recs = engine.run_rows(master, inventory, sales, CFG, run_date)
    run_id = f"{run_date}_{datetime.now(IST):%H%M%S}"
    meta["run_id"] = run_id
    data = json.loads(json.dumps({"meta": meta, "recs": recs}, default=str))
    cur.execute("INSERT INTO runs (run_id, run_date, inventory_as_of, stopped, data) VALUES (%s, %s, %s, %s, %s)",
                (run_id, run_date, meta["inventory_as_of"] if meta["inventory_as_of"] != "None" else None,
                 bool(meta["stops"]), Jsonb(data)))
    counts = {}
    for r in recs:
        counts[r["route"]] = counts.get(r["route"], 0) + 1
    alert = None if meta["stops"] else ops.engine_alerts(cur, run_id, data["recs"])
    return {"run_id": run_id, "stops": meta["stops"], "sku_issues": meta["sku_issues"],
            "warnings": meta["warnings"], "counts": counts, "alert": alert}


def add_decision(cur, body):
    run_id, data = load_run(cur, body.get("run_id"))
    if data["meta"]["stops"]:
        raise ValueError("This run was stopped by data checks; nothing to approve")
    row = validate_decision(run_id, data["recs"], body, CFG["reason_codes"])
    row.pop("decided_at")
    row["alt_qty"] = row["alt_qty"] if row["alt_qty"] != "" else None
    cols = list(row)
    cur.execute(f"INSERT INTO decisions ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING decided_at",
                [row[c] for c in cols])
    row["decided_at"] = cur.fetchone()["decided_at"].astimezone(IST).isoformat(timespec="seconds")
    return row


def zoho(cur, body):
    run_id, data = load_run(cur, body.get("run_id"))
    lines, pending = zoho_lines(run_id, data, latest_decisions(cur, run_id))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=ZOHO_COLS)
    w.writeheader()
    w.writerows(lines)
    return {"run_id": run_id, "lines": lines, "pending": pending, "csv": buf.getvalue(),
            "filename": f"zoho_po_drafts_{run_id}.csv", "pos": len({x["Purchase Order Number"] for x in lines})}


def decisions_csv(cur):
    cur.execute("SELECT * FROM decisions ORDER BY id")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=LOG_COLS, extrasaction="ignore")
    w.writeheader()
    for r in cur.fetchall():
        r["decided_at"] = r["decided_at"].astimezone(IST).isoformat(timespec="seconds")
        w.writerow(r)
    return buf.getvalue()


class handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else json.dumps(body, default=to_json).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def route(self, method):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        # On Vercel the rewrite hands the original path over as ?route=; locally it is the path itself.
        path = ("/api/" + query["route"][0]) if "route" in query else url.path
        path = path.rstrip("/")
        body = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            if length > 8 * 1024 * 1024:
                return self.send(413, {"error": "Upload too large (8 MB limit)"})
            body = json.loads(self.rfile.read(length) or b"{}")
        try:
            with db() as conn, conn.cursor() as cur:
                if method == "GET" and path == "/api/runs":
                    return self.send(200, list_runs(cur))
                if method == "GET" and path == "/api/run":
                    run_id, data = load_run(cur, query.get("id", [None])[0])
                    return self.send(200, {**data, "decisions": latest_decisions(cur, run_id),
                                           "reason_codes": CFG["reason_codes"]})
                if method == "GET" and path == "/api/decisions.csv":
                    return self.send(200, decisions_csv(cur), "text/csv")
                if method == "POST" and path == "/api/run":
                    return self.send(200, create_run(cur, body))
                if method == "POST" and path == "/api/decision":
                    return self.send(200, add_decision(cur, body))
                if method == "POST" and path == "/api/zoho":
                    return self.send(200, zoho(cur, body))
                status = query.get("status", [None])[0]
                if method == "GET" and path == "/api/queries":
                    return self.send(200, {"queries": ops.list_queries(cur, status), "stats": ops.query_stats(cur)})
                if method == "GET" and path == "/api/queries.csv":
                    return self.send(200, ops.queries_csv(cur), "text/csv")
                if method == "POST" and path == "/api/queries":
                    return self.send(200, ops.log_query(cur, body))
                if method == "POST" and path == "/api/queries/update":
                    return self.send(200, ops.update_query(cur, body))
                if method == "GET" and path == "/api/metrics":
                    return self.send(200, ops.list_metrics(cur))
                if method == "POST" and path == "/api/metrics/update":
                    return self.send(200, ops.update_metric(cur, body))
                if method == "GET" and path == "/api/alerts":
                    return self.send(200, {"alerts": ops.list_alerts(cur, status), "summary": ops.alert_summary(cur),
                                           "recent_48h": ops.recent_alerts(cur)})
                if method == "POST" and path == "/api/alerts":
                    return self.send(200, ops.raise_alert(cur, body))
                if method == "POST" and path == "/api/alerts/update":
                    return self.send(200, ops.update_alert(cur, body))
            return self.send(404, {"error": "Not found"})
        except LookupError as e:
            return self.send(404, {"error": str(e)})
        except (ValueError, KeyError) as e:
            return self.send(400, {"error": str(e)})

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")
