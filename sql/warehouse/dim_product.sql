CREATE TABLE IF NOT EXISTS analytics.dim_product (
    product_key BIGINT GENERATED ALWAYS AS IDENTITY,
    product_id TEXT NULL,
    name TEXT NOT NULL,
    description TEXT,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    is_current BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT pk_dim_product
        PRIMARY KEY (product_key),
    CONSTRAINT ck_dim_product_validity
        CHECK (valid_to IS NULL OR valid_from < valid_to)
    CONSTRAINT ck_dim_product_current_validity
        CHECK (
            (is_current AND valid_to IS NULL)
            OR
            (NOT is_current AND valid_to IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_product_current
    ON analytics.dim_product (product_id)
    WHERE is_current;