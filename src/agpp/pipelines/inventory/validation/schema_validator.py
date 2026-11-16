"""Feed-level check of the fields found by extraction."""

from agpp.pipelines.inventory.validation.schema import REQUIRED_COLUMNS
from agpp.shared.exceptions import SchemaValidationError


def validate_schema(columns: tuple[str, ...], source: str) -> tuple[str, ...]:
    """Require every contract field; return the extra fields that will be ignored."""
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise SchemaValidationError(
            f"Stock feed is missing required fields: {missing}",
            context={"source": source, "missing_columns": missing},
        )
    return tuple(name for name in columns if name and name not in REQUIRED_COLUMNS)
