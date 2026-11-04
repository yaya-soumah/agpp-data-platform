"""Row-level parsing of raw records into ``SupplierProduct`` (ADR-0012)."""

from collections.abc import Iterable

from pydantic import ValidationError

from agpp.pipelines.supplier_product.extraction import RawRecord
from agpp.pipelines.supplier_product.models import SupplierProduct
from agpp.pipelines.supplier_product.validation.result import (
    ParsedRecord,
    RejectedRecord,
    RejectionStage,
)
from agpp.pipelines.supplier_product.validation.schema import KNOWN_COLUMNS, OPTIONAL_COLUMNS


def parse_records(
    supplier_id: str, records: Iterable[RawRecord]
) -> tuple[list[ParsedRecord], list[RejectedRecord]]:
    """Parse each record; return the ones that parsed and the ones rejected.

    Columns outside the contract are ignored, a blank optional cell uses the
    model's default, and ``supplier_id`` always comes from the configuration.
    """
    parsed: list[ParsedRecord] = []
    rejected: list[RejectedRecord] = []
    for record in records:
        if record.problem is not None:
            rejected.append(_reject(supplier_id, record, (record.problem,)))
            continue
        values = {
            name: value
            for name, value in record.values.items()
            if name in KNOWN_COLUMNS and not (name in OPTIONAL_COLUMNS and not value.strip())
        }
        try:
            product = SupplierProduct.model_validate({**values, "supplier_id": supplier_id})
        except ValidationError as error:
            rejected.append(_reject(supplier_id, record, _describe(error)))
            continue
        parsed.append(ParsedRecord(record.line_number, record.values, product))
    return parsed, rejected


def _reject(supplier_id: str, record: RawRecord, reasons: tuple[str, ...]) -> RejectedRecord:
    return RejectedRecord(
        supplier_id, record.line_number, RejectionStage.PARSING, reasons, record.values
    )


def _describe(error: ValidationError) -> tuple[str, ...]:
    """Field and rule only, never the offending input value."""
    return tuple(
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in error.errors()
    )
