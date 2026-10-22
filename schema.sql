-- Neon Postgres schema for the hosted engine. Runs are stored whole; decisions are append-only.
CREATE TABLE IF NOT EXISTS runs (
  run_id          text PRIMARY KEY,
  run_date        date NOT NULL,
  inventory_as_of date,
  stopped         boolean NOT NULL DEFAULT false,
  data            jsonb NOT NULL,            -- {"meta": {...}, "recs": [...]} exactly as engine.run returns
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decisions (
  id            bigserial PRIMARY KEY,
  run_id        text NOT NULL REFERENCES runs(run_id),
  decided_at    timestamptz NOT NULL DEFAULT now(),
  reviewer      text NOT NULL,
  sku           text NOT NULL,
  route         text NOT NULL,
  flags         text NOT NULL DEFAULT '',
  system_action text NOT NULL,
  system_qty    integer NOT NULL,
  alt_qty       integer,
  decision      text NOT NULL CHECK (decision IN ('APPROVE', 'OVERRIDE', 'REJECT')),
  final_qty     integer NOT NULL CHECK (final_qty >= 0),
  reason_code   text NOT NULL DEFAULT '',
  note          text NOT NULL DEFAULT '',
  on_hand       double precision,
  avg_12w       double precision,
  cover_weeks   double precision
);

CREATE INDEX IF NOT EXISTS decisions_run_sku ON decisions (run_id, sku, id);

-- Distributor query log: every WhatsApp query, so Distributor Service has data before anything is automated.
CREATE TABLE IF NOT EXISTS dist_queries (
  id                bigserial PRIMARY KEY,
  received_at       timestamptz NOT NULL,
  sla_due_at        timestamptz NOT NULL,      -- first reply due: 2 working hours (Mon-Sat 9:00-19:00 IST)
  distributor       text NOT NULL,
  region            text NOT NULL DEFAULT '',
  channel           text NOT NULL DEFAULT 'WhatsApp',
  category          text NOT NULL CHECK (category IN ('Order status', 'Delivery ETA', 'Scheme eligibility',
                      'Returns or credit note', 'Invoice or pricing', 'Complaint', 'Other')),
  summary           text NOT NULL,
  assigned_to       text NOT NULL,
  status            text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESPONDED', 'RESOLVED')),
  first_response_at timestamptz,
  resolved_at       timestamptz,
  resolution        text NOT NULL DEFAULT '',
  logged_by         text NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS query_events (
  id        bigserial PRIMARY KEY,
  query_id  bigint NOT NULL REFERENCES dist_queries(id),
  at        timestamptz NOT NULL DEFAULT now(),
  by_name   text NOT NULL,
  kind      text NOT NULL CHECK (kind IN ('LOGGED', 'RESPONDED', 'REASSIGNED', 'RESOLVED', 'REOPENED')),
  note      text NOT NULL DEFAULT ''
);

-- Metric owner register: one owner per metric, with trigger, action and deadline.
CREATE TABLE IF NOT EXISTS metric_owners (
  metric_id      text PRIMARY KEY,
  metric         text NOT NULL,
  owner_role     text NOT NULL,
  owner_name     text NOT NULL DEFAULT '',
  trigger_text   text NOT NULL,
  action_text    text NOT NULL,
  deadline_hours integer NOT NULL CHECK (deadline_hours > 0),
  escalate_to    text NOT NULL DEFAULT 'Deepa Nair',
  sort_order     integer NOT NULL DEFAULT 0,
  updated_at     timestamptz NOT NULL DEFAULT now()
);

-- Alerts: raised against a metric, acknowledged by its owner with the action taken, escalated past the deadline.
CREATE TABLE IF NOT EXISTS alerts (
  id               bigserial PRIMARY KEY,
  metric_id        text NOT NULL REFERENCES metric_owners(metric_id),
  source           text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'engine', 'po_gate')),
  title            text NOT NULL,
  detail           text NOT NULL DEFAULT '',
  raised_by        text NOT NULL,
  raised_at        timestamptz NOT NULL DEFAULT now(),
  due_at           timestamptz NOT NULL,
  owner_role       text NOT NULL,             -- copied at raise time, so a later owner change keeps history
  owner_name       text NOT NULL DEFAULT '',
  status           text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
  escalated_at     timestamptz,
  acknowledged_at  timestamptz,
  acknowledged_by  text,
  action_taken     text,
  resolved_at      timestamptz,
  resolved_by      text,
  resolution       text,
  run_id           text REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS alerts_status ON alerts (status, due_at);
CREATE INDEX IF NOT EXISTS dist_queries_received ON dist_queries (received_at DESC);
