-- Run bookkeeping (ADR-0014): what each pipeline run did, per supplier.
CREATE TABLE operational.pipeline_runs (
    run_id      text        PRIMARY KEY,
    pipeline    text        NOT NULL,
    status      text        NOT NULL CHECK (status IN ('running', 'succeeded', 'partial', 'failed')),
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);

CREATE TABLE operational.supplier_run_results (
    run_id             text        NOT NULL REFERENCES operational.pipeline_runs (run_id),
    supplier_id        text        NOT NULL,
    status             text        NOT NULL CHECK (status IN ('loaded', 'failed')),
    failed_stage       text,
    error_message      text,
    rows_read          integer,
    valid_rows         integer,
    rejected_rows      integer,
    products_written   integer,
    products_unchanged integer,
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, supplier_id),
    CONSTRAINT supplier_run_results_stage_matches_status
        CHECK ((status = 'loaded') = (failed_stage IS NULL))
);

COMMENT ON TABLE operational.pipeline_runs IS 'One row per pipeline run.';
COMMENT ON TABLE operational.supplier_run_results IS
    'One row per supplier and run: loaded with counts, or failed with stage and message.';
