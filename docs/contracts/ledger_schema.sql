CREATE TABLE events (
  event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  event_uid      TEXT    NOT NULL UNIQUE,
  occurred_at    TEXT    NOT NULL,
  type           TEXT    NOT NULL CHECK (type IN (
    'merchant.onboarded','customer.created',
    'payment.authorized','payment.captured','payment.failed',
    'payment.refunded','payment.partially_refunded','refund.requested','refund.rejected','fx.applied',
    'chargeback.opened','chargeback.evidence_requested','chargeback.evidence_submitted',
    'chargeback.won','chargeback.lost',
    'settlement.settled','payout.paid')),
  aggregate_type TEXT    NOT NULL CHECK (aggregate_type IN
    ('merchant','customer','transaction','refund','chargeback','settlement')),
  aggregate_id   TEXT    NOT NULL,
  payload        TEXT    NOT NULL CHECK (json_valid(payload)),
  origin         TEXT    NOT NULL,
  ingested_at    TEXT    NOT NULL
);
CREATE INDEX idx_events_aggregate ON events (aggregate_type, aggregate_id, event_id);
CREATE INDEX idx_events_time ON events (occurred_at);
CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
CREATE TABLE projector_state (name TEXT PRIMARY KEY, last_event_id INTEGER NOT NULL);

CREATE TABLE merchants (
  id TEXT PRIMARY KEY CHECK (id GLOB 'M-[0-9][0-9]'),
  name TEXT NOT NULL,
  country TEXT NOT NULL CHECK (length(country) = 2),
  category TEXT NOT NULL CHECK (category IN ('travel','saas','retail','food','gaming','marketplace')),
  settlement_currency TEXT NOT NULL CHECK (length(settlement_currency) = 3),
  fx_plan TEXT NOT NULL CHECK (fx_plan IN ('standard','markup')),
  refund_window_days INTEGER NOT NULL DEFAULT 30 CHECK (refund_window_days > 0),
  onboarded_at TEXT NOT NULL
);
CREATE TABLE customers (
  id TEXT PRIMARY KEY CHECK (id GLOB 'C-[0-9][0-9][0-9][0-9]'),
  display_name TEXT NOT NULL,
  country TEXT NOT NULL CHECK (length(country) = 2),
  billing_currency TEXT NOT NULL CHECK (length(billing_currency) = 3),
  created_at TEXT NOT NULL
);
CREATE TABLE transactions (
  id TEXT PRIMARY KEY CHECK (id GLOB 'TX-[0-9][0-9][0-9][0-9]'),
  merchant_id TEXT NOT NULL REFERENCES merchants (id),
  customer_id TEXT NOT NULL REFERENCES customers (id),
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  currency TEXT NOT NULL CHECK (length(currency) = 3),
  method TEXT NOT NULL CHECK (method IN ('card','boleto','pix','wallet','bank_transfer','voucher')),
  card_brand TEXT CHECK (card_brand IN ('visa','mastercard','amex','elo','other')),
  card_fingerprint TEXT,
  status TEXT NOT NULL CHECK (status IN ('authorized','captured','failed','refunded','partially_refunded','disputed','charged_back')),
  created_at TEXT NOT NULL,
  captured_at TEXT,
  origin TEXT NOT NULL,
  source_ref TEXT
);
CREATE INDEX idx_tx_customer ON transactions (customer_id, created_at);
CREATE INDEX idx_tx_merchant ON transactions (merchant_id, created_at);
CREATE INDEX idx_tx_fingerprint ON transactions (card_fingerprint, merchant_id, created_at);
CREATE TABLE fx_applied (
  id TEXT PRIMARY KEY CHECK (id GLOB 'FX-[0-9][0-9][0-9][0-9]*'),
  transaction_id TEXT NOT NULL REFERENCES transactions (id),
  refund_id TEXT,
  kind TEXT NOT NULL CHECK (kind IN ('charge','refund')),
  from_currency TEXT NOT NULL CHECK (length(from_currency) = 3),
  to_currency TEXT NOT NULL CHECK (length(to_currency) = 3),
  applied_rate TEXT NOT NULL CHECK (applied_rate GLOB '[0-9]*.[0-9]*'),
  applied_at TEXT NOT NULL
);
CREATE TABLE refunds (
  id TEXT PRIMARY KEY CHECK (id GLOB 'R-[0-9][0-9][0-9][0-9]'),
  transaction_id TEXT NOT NULL REFERENCES transactions (id),
  requested_amount_minor INTEGER NOT NULL CHECK (requested_amount_minor > 0),
  requested_currency TEXT NOT NULL CHECK (length(requested_currency) = 3),
  payout_amount_minor INTEGER CHECK (payout_amount_minor >= 0),
  payout_currency TEXT CHECK (length(payout_currency) = 3),
  fx_applied_id TEXT REFERENCES fx_applied (id),
  status TEXT NOT NULL CHECK (status IN ('requested','paid','rejected')),
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE INDEX idx_refunds_tx ON refunds (transaction_id);
CREATE TABLE chargebacks (
  id TEXT PRIMARY KEY CHECK (id GLOB 'CB-[0-9][0-9][0-9][0-9]'),
  transaction_id TEXT NOT NULL REFERENCES transactions (id),
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  currency TEXT NOT NULL CHECK (length(currency) = 3),
  reason_code TEXT NOT NULL CHECK (reason_code IN ('FRD','DUP','NRC','NAD','OTH')),
  stage TEXT NOT NULL CHECK (stage IN ('opened','evidence_requested','evidence_submitted','won','lost')),
  opened_at TEXT NOT NULL,
  deadline TEXT NOT NULL,
  resolved_at TEXT
);
CREATE INDEX idx_cb_tx ON chargebacks (transaction_id);
CREATE TABLE settlements (
  id TEXT PRIMARY KEY CHECK (id GLOB 'ST-[0-9][0-9][0-9][0-9]'),
  merchant_id TEXT NOT NULL REFERENCES merchants (id),
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  currency TEXT NOT NULL CHECK (length(currency) = 3),
  gross_minor INTEGER NOT NULL,
  refunds_minor INTEGER NOT NULL,
  fees_minor INTEGER NOT NULL,
  net_minor INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('scheduled','paid')),
  expected_payout_date TEXT NOT NULL,
  paid_at TEXT,
  CHECK (net_minor = gross_minor - refunds_minor - fees_minor),
  UNIQUE (merchant_id, period_start)
);
