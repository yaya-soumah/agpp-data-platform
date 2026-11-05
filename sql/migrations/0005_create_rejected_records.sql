-- Records rejected by validation, kept per run so suppliers can be asked to fix them
-- (ADR-0012). Operational data: short retention, not part of the warehouse.
CREATE TABLE operational.rejected_records (
    rejected_record_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id             text        NOT NULL,
    pipeline           text        NOT NULL,
    supplier_id        text        NOT NULL,
    line_number        integer     NOT NULL,
    stage              text        NOT NULL CHECK (stage IN ('parsing', 'business', 'duplicate')),
    reasons            jsonb       NOT NULL,
    raw_values         jsonb       NOT NULL,
    rejected_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT rejected_records_source_key UNIQUE (run_id, pipeline, supplier_id, line_number)
);

CREATE INDEX rejected_records_supplier_idx
    ON operational.rejected_records (pipeline, supplier_id, rejected_at DESC);

COMMENT ON TABLE operational.rejected_records IS
    'One row per rejected source line per run. reasons is a JSON array of strings.';
