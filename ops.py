"""Distributor query log and metric-owner alerts (the operating plan's two tools).

Everything here takes a psycopg cursor with dict rows; api/index.py routes to it.
Times are stored as timestamptz and returned in IST.
"""
import csv
import io
import statistics
from datetime import datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
CATEGORIES = ["Order status", "Delivery ETA", "Scheme eligibility", "Returns or credit note",
              "Invoice or pricing", "Complaint", "Other"]
ROUTINE = {"Order status", "Delivery ETA", "Scheme eligibility", "Returns or credit note"}
DAY_START, DAY_END = time(9, 0), time(19, 0)       # working hours, Monday to Saturday
FIRST_REPLY_HOURS = 2
GATE_WEEKS, ROUTINE_TARGET = 6, 0.60


def need(body, *keys):
    missing = [k for k in keys if not str(body.get(k) or "").strip()]
    if missing:
        raise ValueError("Missing: " + ", ".join(missing))
    return [str(body[k]).strip() for k in keys]


def ist(dt):
    return dt.astimezone(IST).isoformat(timespec="minutes") if dt else None


def add_working_hours(start, hours):
    """start + hours of Mon-Sat 9:00-19:00 IST. A query after hours starts its clock at 9:00 next working day."""
    t = start.astimezone(IST)
    left = timedelta(hours=hours)
    while True:
        if t.weekday() == 6 or t.time() >= DAY_END:
            t = datetime.combine(t.date() + timedelta(days=1), DAY_START, IST)
            continue
        if t.time() < DAY_START:
            t = datetime.combine(t.date(), DAY_START, IST)
        end_of_day = datetime.combine(t.date(), DAY_END, IST)
        if t + left <= end_of_day:
            return t + left
        left -= end_of_day - t
        t = end_of_day


# ---------------------------------------------------------------- distributor queries

def _query_row(r, now):
    replied = r["first_response_at"]
    r["sla_met"] = None if replied is None and now <= r["sla_due_at"] else bool(replied and replied <= r["sla_due_at"])
    r["minutes_to_reply"] = round((replied - r["received_at"]).total_seconds() / 60) if replied else None
    for k in ("received_at", "sla_due_at", "first_response_at", "resolved_at", "created_at"):
        r[k] = ist(r[k])
    return r


def list_queries(cur, status=None):
    now = datetime.now(timezone.utc)
    where, args = "", []
    if status in ("OPEN", "RESPONDED", "RESOLVED"):
        where, args = "WHERE status = %s", [status]
    elif status == "active":
        where = "WHERE status <> 'RESOLVED'"
    cur.execute(f"SELECT * FROM dist_queries {where} ORDER BY received_at DESC LIMIT 300", args)
    return [_query_row(r, now) for r in cur.fetchall()]


def query_stats(cur):
    now = datetime.now(timezone.utc)
    cur.execute("SELECT * FROM dist_queries WHERE received_at > now() - interval '42 days'")
    rows = cur.fetchall()
    total = len(rows)
    by_cat = {c: sum(r["category"] == c for r in rows) for c in CATEGORIES}
    due = [r for r in rows if r["first_response_at"] or now > r["sla_due_at"]]
    met = [r for r in due if r["first_response_at"] and r["first_response_at"] <= r["sla_due_at"]]
    mins = [(r["first_response_at"] - r["received_at"]).total_seconds() / 60 for r in rows if r["first_response_at"]]
    cur.execute("SELECT min(received_at) AS first FROM dist_queries")
    first = cur.fetchone()["first"]
    weeks = round((now - first).days / 7, 1) if first else 0
    open_by = {}
    for r in rows:
        if r["status"] != "RESOLVED":
            open_by[r["assigned_to"]] = open_by.get(r["assigned_to"], 0) + 1
    routine = sum(by_cat[c] for c in ROUTINE)
    return {
        "total_6w": total, "by_category": by_cat,
        "routine_share": round(routine / total, 3) if total else None,
        "sla_met_share": round(len(met) / len(due), 3) if due else None,
        "median_minutes_to_reply": round(statistics.median(mins)) if mins else None,
        "open_by_assignee": open_by, "weeks_of_data": weeks,
        "gate": {"weeks_needed": GATE_WEEKS, "routine_target": ROUTINE_TARGET,
                 "ready": weeks >= GATE_WEEKS,
                 "verdict": None if weeks < GATE_WEEKS or not total else
                 ("automate" if routine / total >= ROUTINE_TARGET else "do not automate")},
        "categories": CATEGORIES,
    }


def log_query(cur, body):
    distributor, category, summary, assigned_to, logged_by = need(
        body, "distributor", "category", "summary", "assigned_to", "logged_by")
    if category not in CATEGORIES:
        raise ValueError("Category must be one of: " + ", ".join(CATEGORIES))
    if body.get("received_at"):
        received = datetime.fromisoformat(body["received_at"])
        received = received.replace(tzinfo=IST) if received.tzinfo is None else received
        if received > datetime.now(IST) + timedelta(minutes=5):
            raise ValueError("Received time is in the future")
    else:
        received = datetime.now(IST)
    cur.execute("""INSERT INTO dist_queries (received_at, sla_due_at, distributor, region, channel, category,
                     summary, assigned_to, logged_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (received, add_working_hours(received, FIRST_REPLY_HOURS), distributor,
                 str(body.get("region") or "").strip(), str(body.get("channel") or "WhatsApp").strip(),
                 category, summary, assigned_to, logged_by))
    qid = cur.fetchone()["id"]
    cur.execute("INSERT INTO query_events (query_id, by_name, kind) VALUES (%s, %s, 'LOGGED')", (qid, logged_by))
    return get_query(cur, qid)


def get_query(cur, qid):
    cur.execute("SELECT * FROM dist_queries WHERE id = %s", (qid,))
    r = cur.fetchone()
    if r is None:
        raise LookupError("No such query")
    r = _query_row(r, datetime.now(timezone.utc))
    cur.execute("SELECT at, by_name, kind, note FROM query_events WHERE query_id = %s ORDER BY id", (qid,))
    r["events"] = [{**e, "at": ist(e["at"])} for e in cur.fetchall()]
    return r


def update_query(cur, body):
    (by,) = need(body, "by")
    action = body.get("action")
    cur.execute("SELECT * FROM dist_queries WHERE id = %s FOR UPDATE", (int(body.get("id") or 0),))
    q = cur.fetchone()
    if q is None:
        raise LookupError("No such query")
    note = str(body.get("note") or "").strip()
    if action == "respond":
        if q["first_response_at"]:
            raise ValueError("First reply already recorded")
        cur.execute("UPDATE dist_queries SET first_response_at = now(), status = 'RESPONDED' WHERE id = %s", (q["id"],))
        kind = "RESPONDED"
    elif action == "reassign":
        (to,) = need(body, "assigned_to")
        if to == q["assigned_to"]:
            raise ValueError("Already assigned to " + to)
        cur.execute("UPDATE dist_queries SET assigned_to = %s WHERE id = %s", (to, q["id"]))
        kind, note = "REASSIGNED", f"{q['assigned_to']} → {to}" + (f": {note}" if note else "")
    elif action == "resolve":
        if not note:
            raise ValueError("Say how it was resolved")
        cur.execute("""UPDATE dist_queries SET status = 'RESOLVED', resolved_at = now(), resolution = %s,
                       first_response_at = COALESCE(first_response_at, now()) WHERE id = %s""", (note, q["id"]))
        kind = "RESOLVED"
    elif action == "reopen":
        if q["status"] != "RESOLVED":
            raise ValueError("Only a resolved query can be reopened")
        cur.execute("UPDATE dist_queries SET status = 'RESPONDED', resolved_at = NULL WHERE id = %s", (q["id"],))
        kind = "REOPENED"
    else:
        raise ValueError("action must be respond, reassign, resolve or reopen")
    cur.execute("INSERT INTO query_events (query_id, by_name, kind, note) VALUES (%s, %s, %s, %s)", (q["id"], by, kind, note))
    return get_query(cur, q["id"])


QUERY_COLS = ["id", "received_at", "sla_due_at", "distributor", "region", "channel", "category", "summary",
              "assigned_to", "status", "first_response_at", "resolved_at", "resolution", "logged_by", "sla_met", "minutes_to_reply"]


def queries_csv(cur):
    cur.execute("SELECT * FROM dist_queries ORDER BY received_at")
    now = datetime.now(timezone.utc)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=QUERY_COLS, extrasaction="ignore")
    w.writeheader()
    w.writerows(_query_row(r, now) for r in cur.fetchall())
    return buf.getvalue()


# ---------------------------------------------------------------- metric owners and alerts

def list_metrics(cur):
    cur.execute("SELECT * FROM metric_owners ORDER BY sort_order")
    return [{**m, "updated_at": ist(m["updated_at"])} for m in cur.fetchall()]


def update_metric(cur, body):
    metric_id, by = need(body, "metric_id", "by")
    fields = {k: str(body[k]).strip() for k in ("owner_name", "escalate_to") if k in body}
    if not fields:
        raise ValueError("Nothing to change: send owner_name or escalate_to")
    if "escalate_to" in fields and not fields["escalate_to"]:
        raise ValueError("Every metric needs someone to escalate to")
    sets = ", ".join(f"{k} = %s" for k in fields)
    cur.execute(f"UPDATE metric_owners SET {sets}, updated_at = now() WHERE metric_id = %s RETURNING *",
                [*fields.values(), metric_id])
    row = cur.fetchone()
    if row is None:
        raise LookupError("No such metric")
    return {**row, "updated_at": ist(row["updated_at"])}


def escalate_overdue(cur):
    """Escalation is applied whenever alerts are read, so it needs no scheduler."""
    cur.execute("UPDATE alerts SET escalated_at = now() WHERE status = 'OPEN' AND due_at < now() AND escalated_at IS NULL")


def _alert_row(a):
    a["late"] = bool(a["acknowledged_at"] and a["acknowledged_at"] > a["due_at"])
    for k in ("raised_at", "due_at", "escalated_at", "acknowledged_at", "resolved_at"):
        a[k] = ist(a[k])
    return a


def list_alerts(cur, status=None):
    escalate_overdue(cur)
    where, args = "", []
    if status in ("OPEN", "ACKNOWLEDGED", "RESOLVED"):
        where, args = "WHERE a.status = %s", [status]
    elif status == "active":
        where = "WHERE a.status <> 'RESOLVED'"
    elif status == "escalated":
        where = "WHERE a.status = 'OPEN' AND a.escalated_at IS NOT NULL"
    cur.execute(f"""SELECT a.*, m.metric, m.escalate_to, m.action_text FROM alerts a JOIN metric_owners m USING (metric_id)
                    {where} ORDER BY (a.status = 'OPEN') DESC, a.due_at LIMIT 300""", args)
    return [_alert_row(a) for a in cur.fetchall()]


def alert_summary(cur):
    escalate_overdue(cur)
    cur.execute("""SELECT count(*) FILTER (WHERE status = 'OPEN') AS open,
                          count(*) FILTER (WHERE status = 'OPEN' AND escalated_at IS NOT NULL) AS escalated,
                          count(*) FILTER (WHERE status = 'ACKNOWLEDGED') AS acknowledged,
                          count(*) FILTER (WHERE acknowledged_at IS NOT NULL) AS acked_total,
                          count(*) FILTER (WHERE acknowledged_at IS NOT NULL AND acknowledged_at <= due_at) AS acked_on_time,
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM acknowledged_at - raised_at) / 3600)
                            FILTER (WHERE acknowledged_at IS NOT NULL) AS median_hours_to_ack
                   FROM alerts WHERE raised_at > now() - interval '90 days'""")
    s = cur.fetchone()
    s["on_time_share"] = round(s["acked_on_time"] / s["acked_total"], 3) if s["acked_total"] else None
    s["median_hours_to_ack"] = round(s["median_hours_to_ack"], 1) if s["median_hours_to_ack"] is not None else None
    cur.execute("SELECT count(*) AS n FROM alerts WHERE metric_id = 'po_gate' AND status = 'OPEN'")
    s["po_awaiting_signoff"] = cur.fetchone()["n"]
    return s


def recent_alerts(cur, hours=48):
    cur.execute("""SELECT a.id, a.title, a.status, a.owner_role, m.metric, a.raised_at FROM alerts a JOIN metric_owners m USING (metric_id)
                   WHERE a.metric_id <> 'po_gate' AND a.raised_at > now() - make_interval(hours => %s) ORDER BY a.raised_at DESC""", (hours,))
    return [{**a, "raised_at": ist(a["raised_at"])} for a in cur.fetchall()]


def raise_alert(cur, body, source="manual", run_id=None):
    metric_id, title, raised_by = need(body, "metric_id", "title", "raised_by")
    cur.execute("SELECT * FROM metric_owners WHERE metric_id = %s", (metric_id,))
    m = cur.fetchone()
    if m is None:
        raise LookupError("No such metric")
    if metric_id == "po_gate":
        source = "po_gate"
    cur.execute("""INSERT INTO alerts (metric_id, source, title, detail, raised_by, due_at, owner_role, owner_name, run_id)
                   VALUES (%s, %s, %s, %s, %s, now() + make_interval(hours => %s), %s, %s, %s) RETURNING id""",
                (metric_id, source, title, str(body.get("detail") or "").strip(), raised_by,
                 m["deadline_hours"], m["owner_role"], m["owner_name"], run_id))
    aid = cur.fetchone()["id"]
    return get_alert(cur, aid)


def get_alert(cur, aid):
    cur.execute("""SELECT a.*, m.metric, m.escalate_to, m.action_text FROM alerts a JOIN metric_owners m USING (metric_id)
                   WHERE a.id = %s""", (aid,))
    a = cur.fetchone()
    if a is None:
        raise LookupError("No such alert")
    return _alert_row(a)


def update_alert(cur, body):
    (by,) = need(body, "by")
    action = body.get("action")
    note = str(body.get("note") or "").strip()
    escalate_overdue(cur)
    cur.execute("SELECT * FROM alerts WHERE id = %s FOR UPDATE", (int(body.get("id") or 0),))
    a = cur.fetchone()
    if a is None:
        raise LookupError("No such alert")
    if action == "acknowledge":
        if a["status"] != "OPEN":
            raise ValueError("This alert is already " + a["status"].lower())
        if not note:
            raise ValueError("Say what action you took or will take")
        cur.execute("""UPDATE alerts SET status = 'ACKNOWLEDGED', acknowledged_at = now(), acknowledged_by = %s,
                       action_taken = %s WHERE id = %s""", (by, note, a["id"]))
    elif action == "resolve":
        if a["status"] == "RESOLVED":
            raise ValueError("Already resolved")
        if a["status"] == "OPEN":
            raise ValueError("Acknowledge it with the action taken before resolving")
        if not note:
            raise ValueError("Say how it was resolved")
        cur.execute("UPDATE alerts SET status = 'RESOLVED', resolved_at = now(), resolved_by = %s, resolution = %s WHERE id = %s",
                    (by, note, a["id"]))
    else:
        raise ValueError("action must be acknowledge or resolve")
    return get_alert(cur, a["id"])


def engine_alerts(cur, run_id, recs):
    """After an engine run: one stockout alert for A-class SKUs at risk, routed to the demand planner."""
    hot = [r for r in recs if str(r.get("segment", "")).startswith("A") and "STOCKOUT_RISK" in r.get("flags", [])]
    if not hot:
        return None
    lines = [f"{r['sku']} {r['name']}: {r['cover_weeks']} wks cover" + (" (EXPEDITE)" if "EXPEDITE" in r["flags"] else "")
             for r in sorted(hot, key=lambda r: r["cover_weeks"])]
    return raise_alert(cur, {"metric_id": "stockouts", "raised_by": "Replenishment engine",
                             "title": f"{len(hot)} A-class SKUs at stockout risk in run {run_id}",
                             "detail": "\n".join(lines)}, source="engine", run_id=run_id)
