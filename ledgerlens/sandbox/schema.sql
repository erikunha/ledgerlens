-- The schema of the store of the sandbox: the branches, the events of a branch and the commands of a branch.
--
-- Why it is a file in the repository and not a folder of migrations: the shape of the data travels with the code,
-- so the database of a deployment is brought to the shape of the code with one command, and the command is safe to
-- run twice. Every statement therefore carries `IF NOT EXISTS`: the script may run over a database that already has
-- the schema, and the continuous integration does exactly that.
--
-- The three constraints that carry the promises of the specification:
--
--   * the unique key on `(branch_id, event_uid)` is what makes the append idempotent in the database (FR-011);
--   * the unique key on `(branch_id, idempotency_key)` is what makes a repeated request idempotent (FR-012);
--   * the index on the expiry is what the cleanup job reads (FR-024).

-- The branches: the owner session is a column of the row, so the isolation is a condition of the query and not a
-- folder on the disk.
CREATE TABLE IF NOT EXISTS sandbox_branches (
    branch_id              text        PRIMARY KEY,
    owner_session          text        NOT NULL,
    scenario_id            text        NOT NULL,
    base_snapshot_id       text        NOT NULL,
    base_canonical_hash    text        NOT NULL,
    revision               integer     NOT NULL DEFAULT 0,
    current_canonical_hash text        NOT NULL,
    created_at             timestamptz NOT NULL,
    last_activity_at       timestamptz NOT NULL,
    expires_at             timestamptz NOT NULL,
    state                  text        NOT NULL DEFAULT 'active'
);

-- Every read of a branch filters by the owner session, so this is the index a read of the branches of a visitor
-- uses. The index is created with `IF NOT EXISTS` for the same reason as the tables.
CREATE INDEX IF NOT EXISTS sandbox_branches_owner_session_idx ON sandbox_branches (owner_session);

-- The cleanup job reads the branches whose expiry has passed, whatever their owner (FR-024).
CREATE INDEX IF NOT EXISTS sandbox_branches_expires_at_idx ON sandbox_branches (expires_at);

-- The events of a branch. The key of the table is the branch and the uid of the event, because that pair is what
-- makes an append idempotent (FR-011). The sequence is the order of the append, the same order the file backed
-- store keeps in the lines of its log.
CREATE TABLE IF NOT EXISTS sandbox_events (
    branch_id    text        NOT NULL REFERENCES sandbox_branches (branch_id) ON DELETE CASCADE,
    event_uid    text        NOT NULL,
    event_type   text        NOT NULL,
    aggregate_id text        NOT NULL,
    occurred_at  text        NOT NULL,
    payload      jsonb       NOT NULL,
    origin       text        NOT NULL DEFAULT 'sandbox',
    command_id   text,
    event_seq    bigint      GENERATED ALWAYS AS IDENTITY,
    appended_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sandbox_events_pkey PRIMARY KEY (branch_id, event_uid)
);

-- The commands of a branch. The key of the table is the branch and the idempotency key, because that pair is what
-- makes a repeated request idempotent (FR-012). The table is the home of the answer of a command, so a request
-- that arrives twice reads the answer that was already stored instead of doing the work again.
CREATE TABLE IF NOT EXISTS sandbox_commands (
    branch_id        text        NOT NULL REFERENCES sandbox_branches (branch_id) ON DELETE CASCADE,
    idempotency_key  text        NOT NULL,
    payload_digest   text        NOT NULL,
    revision         integer     NOT NULL,
    canonical_hash   text        NOT NULL,
    response_diff    jsonb       NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sandbox_commands_pkey PRIMARY KEY (branch_id, idempotency_key)
);
