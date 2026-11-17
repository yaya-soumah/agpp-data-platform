-- Periodic snapshot of stock (ADR-0009, ADR-0018): one row per location, product and
-- snapshot date. product_id stays on the fact so that different unknown products, which all
-- share product_key -1, remain distinct rows.
CREATE TABLE warehouse.fact_inventory_snapshot (
    inventory_snapshot_key bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_key               integer     NOT NULL REFERENCES warehouse.dim_date (date_key),
    location_key           integer     NOT NULL REFERENCES warehouse.dim_location (location_key),
    product_id             text        NOT NULL CHECK (product_id ~ '^SUP-[0-9]{3}:.{1,50}$'),
    product_key            integer     NOT NULL REFERENCES warehouse.dim_product (product_key),
    on_hand                integer     NOT NULL CHECK (on_hand BETWEEN 0 AND 1000000),
    reserved               integer     NOT NULL CHECK (reserved BETWEEN 0 AND 1000000),
    available              integer     NOT NULL,
    reorder_point          integer     NOT NULL CHECK (reorder_point BETWEEN 0 AND 1000000),
    below_reorder_point    boolean     NOT NULL,
    snapshot_at            timestamptz NOT NULL,
    source_updated_at      timestamptz NOT NULL,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fact_inventory_snapshot_business_key UNIQUE (date_key, location_key, product_id),
    CONSTRAINT fact_inventory_snapshot_available_matches
        CHECK (reserved <= on_hand AND available = on_hand - reserved),
    CONSTRAINT fact_inventory_snapshot_reorder_flag_matches
        CHECK (below_reorder_point = (available < reorder_point))
);

CREATE INDEX fact_inventory_snapshot_location_idx
    ON warehouse.fact_inventory_snapshot (location_key);
CREATE INDEX fact_inventory_snapshot_product_idx
    ON warehouse.fact_inventory_snapshot (product_key);

COMMENT ON TABLE warehouse.fact_inventory_snapshot IS
    'Grain: one row per location, product and snapshot date (the last snapshot of the day). '
    'Business key: (date_key, location_key, product_id). Unknown products point at product_key -1.';
