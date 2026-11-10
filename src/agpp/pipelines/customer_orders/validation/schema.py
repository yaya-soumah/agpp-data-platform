"""The column contract of the order-lines file (ADR-0016)."""

REQUIRED_COLUMNS: tuple[str, ...] = (
    "order_id",
    "line_number",
    "customer_id",
    "customer_name",
    "customer_country",
    "ordered_at",
    "product_id",
    "quantity",
    "unit_price",
    "currency",
    "status",
    "updated_at",
)
