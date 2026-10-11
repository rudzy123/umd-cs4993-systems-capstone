-- Supports operator queries that filter the queue by status and recency.

CREATE INDEX jobs_status_updated_idx ON jobs (status, updated_at);
