from datetime import UTC, datetime, timedelta
from decimal import Decimal

from agpp.pipelines.customer_orders.config import QualityConfig
from agpp.pipelines.customer_orders.models import OrderLine
from agpp.pipelines.customer_orders.validation.business_validator import (
    validate_business_rules,
)
from agpp.pipelines.customer_orders.validation.result import ParsedLine, RejectionStage

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
QUALITY = QualityConfig(
    max_reject_ratio=0.05,
    allowed_currencies=("EUR", "USD"),
    max_line_amount=Decimal("1000"),
    future_tolerance_minutes=5,
)
VALUES = {
    "order_id": "O-1001",
    "line_number": "1",
    "customer_id": "CUS-00042",
    "customer_name": "Marie Dupont",
    "customer_country": "LU",
    "ordered_at": "2026-11-09T10:00:00Z",
    "product_id": "SUP-001:S1-00012",
    "quantity": "2",
    "unit_price": "10.00",
    "currency": "EUR",
    "status": "placed",
    "updated_at": "2026-11-09T11:00:00Z",
}


def _line(number: int = 2, **overrides: str) -> ParsedLine:
    return ParsedLine(number, {}, OrderLine.model_validate({**VALUES, **overrides}))


def _validate(*lines: ParsedLine) -> tuple[list[ParsedLine], list]:  # type: ignore[type-arg]
    return validate_business_rules(lines, QUALITY, source_id="orders.csv", now=NOW)


def test_a_compliant_line_is_accepted() -> None:
    accepted, rejected = _validate(_line())

    assert len(accepted) == 1
    assert rejected == []


def test_currencies_outside_the_allowed_list_are_rejected() -> None:
    accepted, rejected = _validate(_line(currency="JPY"))

    assert accepted == []
    assert rejected[0].stage is RejectionStage.BUSINESS
    assert rejected[0].reasons[0].startswith("currency: JPY is not allowed")


def test_the_maximum_line_amount_is_allowed_but_not_more() -> None:
    accepted, rejected = _validate(
        _line(2, quantity="10", unit_price="100.00"),
        _line(3, quantity="11", unit_price="100.00"),
    )

    assert [r.line_number for r in accepted] == [2]
    assert [r.line_number for r in rejected] == [3]
    assert "line amount 1100.00 exceeds the maximum" in rejected[0].reasons[0]


def test_timestamps_beyond_the_tolerance_are_rejected() -> None:
    within = (NOW + timedelta(minutes=4)).isoformat()
    beyond = (NOW + timedelta(minutes=6)).isoformat()

    accepted, rejected = _validate(
        _line(2, ordered_at=within, updated_at=within),
        _line(3, ordered_at=beyond, updated_at=beyond),
    )

    assert [r.line_number for r in accepted] == [2]
    assert len(rejected[0].reasons) == 2


def test_an_update_before_the_order_is_rejected() -> None:
    _, rejected = _validate(_line(updated_at="2026-11-09T09:00:00Z"))

    assert rejected[0].reasons == ("updated_at: is before ordered_at",)


def test_orders_outside_the_supported_calendar_are_rejected() -> None:
    _, rejected = _validate(
        _line(ordered_at="1999-12-31T10:00:00Z", updated_at="2026-11-09T11:00:00Z")
    )

    assert "outside the supported calendar" in rejected[0].reasons[0]


def test_every_violated_rule_is_reported() -> None:
    _, rejected = _validate(_line(currency="JPY", quantity="10000", unit_price="999.00"))

    assert len(rejected[0].reasons) == 2
