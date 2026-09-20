-- U08 review candidate only. Do not deploy as a global database without a separate gate.
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA busy_timeout = 5000;

CREATE TABLE schema_meta (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  schema_version INTEGER NOT NULL,
  migrated_at TEXT NOT NULL,
  migration_hash TEXT NOT NULL
);

CREATE TABLE agents (
  agent_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('codex','antigravity')),
  mode TEXT NOT NULL CHECK (mode IN ('managed','standalone','imported')),
  capabilities_json TEXT NOT NULL DEFAULT '{}',
  last_heartbeat_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('ready','busy','degraded','offline')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE tasks (
  task_id TEXT PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  intent_hash TEXT NOT NULL,
  scope_hash TEXT NOT NULL,
  acceptance_hash TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('ready','preflight','leased','running','checkpointed','verifying','succeeded','retry_wait','fallback','failed_safe','blocked_quota','needs_reconciliation')),
  current_owner_id TEXT REFERENCES agents(agent_id),
  current_fencing_token INTEGER NOT NULL DEFAULT 0 CHECK (current_fencing_token >= 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE attempts (
  attempt_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  agent_id TEXT NOT NULL REFERENCES agents(agent_id),
  ordinal INTEGER NOT NULL CHECK (ordinal > 0),
  state TEXT NOT NULL CHECK (state IN ('pending','running','succeeded','failed','orphaned','cancelled')),
  error_class TEXT,
  started_at TEXT,
  finished_at TEXT,
  UNIQUE(task_id, ordinal)
);

CREATE TABLE leases (
  lease_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  owner_id TEXT NOT NULL REFERENCES agents(agent_id),
  fencing_token INTEGER NOT NULL CHECK (fencing_token > 0),
  scope_json TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  renewed_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  released_at TEXT,
  UNIQUE(task_id, fencing_token)
);

CREATE UNIQUE INDEX one_live_lease_per_task
ON leases(task_id) WHERE released_at IS NULL;

CREATE TABLE commands (
  command_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  attempt_id TEXT REFERENCES attempts(attempt_id),
  idempotency_key TEXT NOT NULL UNIQUE,
  command_type TEXT NOT NULL,
  payload_ref TEXT,
  payload_hash TEXT NOT NULL,
  required_fencing_token INTEGER NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('pending','leased','acked','done','failed','needs_reconciliation')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  attempt_id TEXT REFERENCES attempts(attempt_id),
  event_type TEXT NOT NULL,
  fencing_token INTEGER,
  body_hash TEXT NOT NULL,
  body_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TRIGGER events_append_only_update
BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER events_append_only_delete
BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;

CREATE TABLE checkpoints (
  checkpoint_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  fencing_token INTEGER NOT NULL,
  manifest_hash TEXT NOT NULL,
  artifact_ref TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(task_id, ordinal)
);

CREATE TABLE proof_receipts (
  receipt_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  checkpoint_id TEXT REFERENCES checkpoints(checkpoint_id),
  command_id TEXT REFERENCES commands(command_id),
  exit_code INTEGER,
  output_hash TEXT,
  acceptance_hash TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK (verdict IN ('pass','fail','unknown')),
  created_at TEXT NOT NULL
);

CREATE TABLE budgets (
  task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
  max_attempts INTEGER NOT NULL CHECK (max_attempts BETWEEN 1 AND 3),
  attempts_used INTEGER NOT NULL DEFAULT 0 CHECK (attempts_used >= 0),
  max_elapsed_ms INTEGER NOT NULL CHECK (max_elapsed_ms > 0),
  quota_floor_pct INTEGER NOT NULL DEFAULT 10 CHECK (quota_floor_pct BETWEEN 0 AND 100),
  circuit_state TEXT NOT NULL CHECK (circuit_state IN ('closed','open','half_open')),
  circuit_until TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE deliveries (
  delivery_id TEXT PRIMARY KEY,
  direction TEXT NOT NULL CHECK (direction IN ('outbox','inbox')),
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  command_id TEXT REFERENCES commands(command_id),
  idempotency_key TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('pending','claimed','delivered','acked','dead_letter')),
  claimed_by TEXT REFERENCES agents(agent_id),
  claim_expires_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  available_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(direction, idempotency_key)
);

CREATE INDEX deliveries_poll_idx ON deliveries(direction, state, available_at);
CREATE INDEX events_task_idx ON events(task_id, event_id);
CREATE INDEX checkpoints_task_idx ON checkpoints(task_id, ordinal);
