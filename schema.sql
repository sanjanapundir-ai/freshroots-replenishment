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
