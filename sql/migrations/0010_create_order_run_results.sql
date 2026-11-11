-- Result of each Customer Orders run: one file per run (ADR-0016).
CREATE TABLE operational.order_run_results (
    run_id                text        PRIMARY KEY REFERENCES operational.pipeline_runs (run_id),
    status                text        NOT NULL CHECK (status IN ('loaded', 'failed')),
    failed_stage          text,
    error_message         text,
    rows_read             integer,
    valid_rows            integer,
    rejected_rows         integer,
    lines_written         integer,
    lines_unchanged       integer,
    unknown_product_lines integer,
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT order_run_results_stage_matches_status
        CHECK ((status = 'loaded') = (failed_stage IS NULL))
);

COMMENT ON TABLE operational.order_run_results IS
    'One row per Customer Orders run: loaded with counts, or failed with stage and message.';
