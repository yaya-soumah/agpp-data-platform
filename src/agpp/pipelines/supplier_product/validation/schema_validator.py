"""File-level check of the columns found by extraction."""

from agpp.pipelines.supplier_product.extraction import ExtractionResult
from agpp.pipelines.supplier_product.validation.schema import KNOWN_COLUMNS, REQUIRED_COLUMNS
from agpp.shared.exceptions import SchemaValidationError


def validate_schema(result: ExtractionResult) -> tuple[str, ...]:
    """Require every contract column; return the extra columns that will be ignored."""
    missing = [name for name in REQUIRED_COLUMNS if name not in result.columns]
    if missing:
        raise SchemaValidationError(
            f"Supplier file is missing required columns: {missing}",
            context={
                "supplier_id": result.supplier_id,
                "source": result.source,
                "missing_columns": missing,
            },
        )
    return tuple(name for name in result.columns if name and name not in KNOWN_COLUMNS)
