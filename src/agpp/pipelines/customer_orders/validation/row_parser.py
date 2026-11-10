"""Row-level parsing of raw records into ``OrderLine`` (ADR-0012)."""

from collections.abc import Iterable

from pydantic import ValidationError

from agpp.pipelines.customer_orders.models import OrderLine
from agpp.pipelines.customer_orders.validation.result import (
    ParsedLine,
    RejectedRecord,
    RejectionStage,
)
from agpp.pipelines.customer_orders.validation.schema import REQUIRED_COLUMNS
from agpp.shared.extraction import RawRecord


def parse_records(
    source_id: str, records: Iterable[RawRecord]
) -> tuple[list[ParsedLine], list[RejectedRecord]]:
    """Parse each record; return the ones that parsed and the ones rejected.

    Columns outside the contract are ignored.
    """
    parsed: list[ParsedLine] = []
    rejected: list[RejectedRecord] = []
    for record in records:
        if record.problem is not None:
            rejected.append(_reject(source_id, record, (record.problem,)))
            continue
        values = {name: value for name, value in record.values.items() if name in REQUIRED_COLUMNS}
        try:
            line = OrderLine.model_validate(values)
        except ValidationError as error:
            rejected.append(_reject(source_id, record, _describe(error)))
            continue
        parsed.append(ParsedLine(record.line_number, record.values, line))
    return parsed, rejected


def _reject(source_id: str, record: RawRecord, reasons: tuple[str, ...]) -> RejectedRecord:
    return RejectedRecord(
        source_id, record.line_number, RejectionStage.PARSING, reasons, record.values
    )


def _describe(error: ValidationError) -> tuple[str, ...]:
    """Field and rule only, never the offending input value."""
    return tuple(
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in error.errors()
    )
