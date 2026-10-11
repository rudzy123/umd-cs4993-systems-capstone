-- Northstar Job Lab initial schema.
-- Applied by northstar.migrate. Statements are split on semicolons outside dollar quotes.

CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    input_payload JSONB NOT NULL,
    result_payload JSONB,
    error_summary TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    worker_id TEXT,
    idempotency_key TEXT,
    idempotency_fingerprint TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    CONSTRAINT jobs_job_type_known CHECK (
        job_type IN ('sort', 'shortest_path', 'word_frequency', 'fibonacci')
    ),
    CONSTRAINT jobs_status_known CHECK (
        status IN ('queued', 'running', 'succeeded', 'failed', 'retrying', 'cancelled')
    ),
    CONSTRAINT jobs_retry_bounds CHECK (
        retry_count >= 0
        AND max_retries >= 0
        AND max_retries <= 5
        AND retry_count <= max_retries
    ),
    CONSTRAINT jobs_version_positive CHECK (version >= 1),
    CONSTRAINT jobs_error_summary_length CHECK (
        error_summary IS NULL OR char_length(error_summary) <= 400
    ),
    CONSTRAINT jobs_result_matches_status CHECK (
        (status = 'succeeded' AND result_payload IS NOT NULL)
        OR (status <> 'succeeded' AND result_payload IS NULL)
    ),
    CONSTRAINT jobs_failed_has_error CHECK (
        status <> 'failed' OR error_summary IS NOT NULL
    ),
    CONSTRAINT jobs_terminal_has_finished_at CHECK (
        status NOT IN ('succeeded', 'failed', 'cancelled')
        OR finished_at IS NOT NULL
    ),
    CONSTRAINT jobs_active_has_started_at CHECK (
        status IN ('queued', 'cancelled')
        OR started_at IS NOT NULL
    ),
    CONSTRAINT jobs_open_has_no_finished_at CHECK (
        status NOT IN ('queued', 'running', 'retrying')
        OR finished_at IS NULL
    ),
    CONSTRAINT jobs_running_has_worker CHECK (
        status <> 'running' OR worker_id IS NOT NULL
    ),
    CONSTRAINT jobs_idempotency_pair CHECK (
        (
            idempotency_key IS NULL
            AND idempotency_fingerprint IS NULL
        )
        OR (
            idempotency_key IS NOT NULL
            AND idempotency_fingerprint IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX jobs_idempotency_key_idx ON jobs (idempotency_key);

CREATE INDEX jobs_claim_idx ON jobs (created_at, id)
    WHERE status IN ('queued', 'retrying');

CREATE INDEX jobs_created_at_idx ON jobs (created_at DESC);

CREATE TABLE job_attempts (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    worker_id TEXT NOT NULL,
    status TEXT NOT NULL,
    error_summary TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    CONSTRAINT job_attempts_status_known CHECK (
        status IN ('running', 'succeeded', 'failed')
    ),
    CONSTRAINT job_attempts_number_positive CHECK (attempt_number >= 1),
    CONSTRAINT job_attempts_error_length CHECK (
        error_summary IS NULL OR char_length(error_summary) <= 400
    ),
    CONSTRAINT job_attempts_unique_number UNIQUE (job_id, attempt_number)
);

CREATE INDEX job_attempts_job_idx ON job_attempts (job_id, attempt_number);

CREATE TABLE job_events (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    worker_id TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT job_events_reason_length CHECK (char_length(reason) <= 80),
    CONSTRAINT job_events_to_status_known CHECK (
        to_status IN ('queued', 'running', 'succeeded', 'failed', 'retrying', 'cancelled')
    )
);

CREATE INDEX job_events_job_idx ON job_events (job_id, id);

CREATE OR REPLACE FUNCTION enforce_job_status_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;

    IF OLD.status = 'queued' AND NEW.status IN ('running', 'cancelled') THEN
        RETURN NEW;
    ELSIF OLD.status = 'retrying' AND NEW.status IN ('running', 'cancelled') THEN
        RETURN NEW;
    ELSIF OLD.status = 'running' AND NEW.status IN ('succeeded', 'retrying', 'failed') THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'invalid job status transition'
        USING ERRCODE = 'check_violation',
              DETAIL = OLD.status || ' -> ' || NEW.status;
END;
$$;

CREATE TRIGGER jobs_status_transition
BEFORE UPDATE OF status ON jobs
FOR EACH ROW
EXECUTE FUNCTION enforce_job_status_transition();

COMMENT ON TABLE jobs IS 'Validated computational jobs and their current state.';
COMMENT ON TABLE job_attempts IS 'One row per worker claim. History survives later retries.';
COMMENT ON TABLE job_events IS 'Audit log of state transitions. Payloads are not stored here.';
