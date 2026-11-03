import pytest

from agpp.pipelines.supplier_product.extraction import ExtractionResult
from agpp.pipelines.supplier_product.sample_data import COLUMNS
from agpp.pipelines.supplier_product.validation.schema import (
    KNOWN_COLUMNS,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
)
from agpp.pipelines.supplier_product.validation.schema_validator import validate_schema
from agpp.shared.exceptions import SchemaValidationError


def _result(columns: tuple[str, ...]) -> ExtractionResult:
    return ExtractionResult("SUP-001", "file.csv", columns, ())


def test_a_complete_header_passes() -> None:
    assert validate_schema(_result(KNOWN_COLUMNS)) == ()


def test_optional_columns_may_be_absent() -> None:
    assert validate_schema(_result(REQUIRED_COLUMNS)) == ()


def test_column_order_does_not_matter() -> None:
    assert validate_schema(_result(tuple(reversed(KNOWN_COLUMNS)))) == ()


def test_missing_required_columns_raise_with_their_names() -> None:
    columns = tuple(name for name in KNOWN_COLUMNS if name not in {"category", "currency"})

    with pytest.raises(SchemaValidationError) as info:
        validate_schema(_result(columns))

    assert info.value.context["missing_columns"] == ["category", "currency"]
    assert info.value.context["supplier_id"] == "SUP-001"
    assert info.value.retryable is False


def test_an_empty_header_raises() -> None:
    with pytest.raises(SchemaValidationError, match="missing required columns"):
        validate_schema(_result(()))


def test_extra_columns_are_reported_not_rejected() -> None:
    assert validate_schema(_result((*KNOWN_COLUMNS, "color", ""))) == ("color",)


def test_the_sample_data_generator_matches_the_contract() -> None:
    assert set(COLUMNS) == set(KNOWN_COLUMNS)


def test_required_and_optional_columns_do_not_overlap() -> None:
    assert not set(REQUIRED_COLUMNS) & set(OPTIONAL_COLUMNS)
