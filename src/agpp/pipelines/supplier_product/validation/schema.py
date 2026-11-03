"""The column contract of a supplier file (ADR-0010)."""

REQUIRED_COLUMNS: tuple[str, ...] = (
    "supplier_sku",
    "product_name",
    "category",
    "unit_price",
    "currency",
    "lead_time_days",
    "updated_at",
)
OPTIONAL_COLUMNS: tuple[str, ...] = ("min_order_quantity", "is_active")
KNOWN_COLUMNS: tuple[str, ...] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
