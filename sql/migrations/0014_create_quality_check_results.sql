CREATE TABLE operational.quality_check_results (
    result_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          text             NOT NULL,
    check_name      text             NOT NULL,
    status          text             NOT NULL
        CHECK (status IN ('pass', 'warn', 'fail', 'no_data', 'error')),
    value           double precision,
    warn_threshold  double precision NOT NULL,
    fail_threshold  double precision NOT NULL,
    comparison      text             NOT NULL CHECK (comparison IN ('max', 'min')),
    message         text,
    checked_at      timestamptz      NOT NULL DEFAULT now(),
    UNIQUE (run_id, check_name)
);

CREATE INDEX quality_check_results_name_checked_idx
    ON operational.quality_check_results (check_name, checked_at DESC);
