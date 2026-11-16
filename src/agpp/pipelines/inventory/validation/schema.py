"""The field contract of a stock feed item (ADR-0018)."""

REQUIRED_COLUMNS: tuple[str, ...] = (
    "location_code",
    "location_name",
    "location_country",
    "product_id",
    "on_hand",
    "reserved",
    "reorder_point",
    "updated_at",
)
