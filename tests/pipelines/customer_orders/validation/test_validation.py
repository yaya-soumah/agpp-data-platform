import polars as pl
import pytest
from src.pipelines.customer_orders.models import CUSTOMER_SCHEMA
from src.pipelines.customer_orders.validation import (
    DefaultCustomerOrdersDuplicateDetector,
    DefaultCustomerOrdersMissingValueValidator,
    DefaultCustomerOrdersSchemaValidator,
)
from src.shared.exceptions import ValidationError


def test_schema_validator_accepts_matching_schema() -> None:
    data = pl.DataFrame(
        {"customer_id": ["C001"], "name": ["Acme"]},
        schema=CUSTOMER_SCHEMA,
    )

    result = DefaultCustomerOrdersSchemaValidator().validate(
        data, CUSTOMER_SCHEMA, "customers"
    )

    assert result.equals(data)


def test_schema_validator_rejects_missing_column() -> None:
    data = pl.DataFrame({"customer_id": ["C001"]})

    with pytest.raises(ValidationError):
        DefaultCustomerOrdersSchemaValidator().validate(
            data, CUSTOMER_SCHEMA, "customers"
        )


def test_missing_value_validator_separates_invalid_rows() -> None:
    data = pl.DataFrame(
        {
            "customer_id": ["C001", "C002", None],
            "name": ["Acme", " ", "Missing ID"],
        }
    )

    result = DefaultCustomerOrdersMissingValueValidator().validate(data, "customers")

    assert result.valid["customer_id"].to_list() == ["C001"]
    assert result.rejected.height == 2


def test_duplicate_detector_rejects_all_duplicate_ids() -> None:
    data = pl.DataFrame(
        {
            "customer_id": ["C001", "C001", "C002"],
            "name": ["Acme", "Acme duplicate", "Beta"],
        }
    )

    result = DefaultCustomerOrdersDuplicateDetector().detect(data, "customers")

    assert result.valid["customer_id"].to_list() == ["C002"]
    assert result.rejected["customer_id"].to_list() == ["C001", "C001"]
