-- Result of each Inventory run: one feed per run (ADR-0018).
CREATE TABLE operational.inventory_run_results (
    run_id                  text        PRIMARY KEY REFERENCES operational.pipeline_runs (run_id),
    status                  text        NOT NULL CHECK (status IN ('loaded', 'failed')),
    failed_stage            text,
    error_message           text,
    snapshot_at             timestamptz,
    rows_read               integer,
    valid_rows              integer,
    rejected_rows           integer,
    rows_written            integer,
    rows_unchanged          integer,
    unknown_product_rows    integer,
    below_reorder_rows      integer,
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT inventory_run_results_stage_matches_status
        CHECK ((status = 'loaded') = (failed_stage IS NULL))
);

COMMENT ON TABLE operational.inventory_run_results IS
    'One row per Inventory run: loaded with counts, or failed with stage and message.';
