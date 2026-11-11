-- Order line fact (ADR-0009, ADR-0016).
CREATE TABLE warehouse.fact_order_line (
    order_line_key    bigint         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id          text           NOT NULL,
    line_number       integer        NOT NULL CHECK (line_number >= 1),
    customer_key      integer        NOT NULL REFERENCES warehouse.dim_customer (customer_key),
    product_key       integer        NOT NULL REFERENCES warehouse.dim_product (product_key),
    date_key          integer        NOT NULL REFERENCES warehouse.dim_date (date_key),
    quantity          integer        NOT NULL CHECK (quantity BETWEEN 1 AND 10000),
    unit_price        numeric(12, 4) NOT NULL CHECK (unit_price > 0),
    line_amount       numeric(18, 4) NOT NULL CHECK (line_amount > 0),
    currency          text           NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    status            text           NOT NULL
        CHECK (status IN ('placed', 'shipped', 'delivered', 'cancelled')),
    ordered_at        timestamptz    NOT NULL,
    source_updated_at timestamptz    NOT NULL,
    created_at        timestamptz    NOT NULL DEFAULT now(),
    updated_at        timestamptz    NOT NULL DEFAULT now(),
    CONSTRAINT fact_order_line_business_key UNIQUE (order_id, line_number)
);

CREATE INDEX fact_order_line_customer_idx ON warehouse.fact_order_line (customer_key);
CREATE INDEX fact_order_line_product_idx ON warehouse.fact_order_line (product_key);
CREATE INDEX fact_order_line_date_idx ON warehouse.fact_order_line (date_key);

COMMENT ON TABLE warehouse.fact_order_line IS
    'Grain: one row per order line. Business key: (order_id, line_number). '
    'Unknown customers and products point at the -1 members.';
