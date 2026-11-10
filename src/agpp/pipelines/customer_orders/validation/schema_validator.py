"""File-level check of the columns found by extraction."""

from agpp.pipelines.customer_orders.validation.schema import REQUIRED_COLUMNS
from agpp.shared.exceptions import SchemaValidationError


def validate_schema(columns: tuple[str, ...], source: str) -> tuple[str, ...]:
    """Require every contract column; return the extra columns that will be ignored."""
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise SchemaValidationError(
            f"Order file is missing required columns: {missing}",
            context={"source": source, "missing_columns": missing},
        )
    return tuple(name for name in columns if name and name not in REQUIRED_COLUMNS)
