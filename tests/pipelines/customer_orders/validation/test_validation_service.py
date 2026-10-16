from unittest.mock import MagicMock, call

import polars as pl
import pytest
from src.pipelines.customer_orders.extractors.base import CustomerOrdersBatch
from src.pipelines.customer_orders.models import (
    CUSTOMER_SCHEMA,
    ORDER_LINE_SCHEMA,
    ORDER_SCHEMA,
)
from src.pipelines.customer_orders.validation import (
    CustomerOrdersCrossFileValidationResult,
    CustomerOrdersValidationService,
    ValidationResult,
)


def _df(rows: list[dict]) -> pl.DataFrame:
    """Build a DataFrame from a list of row dicts (empty -> schema-less)."""
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows)


def _empty_rejected() -> pl.DataFrame:
    """A 0-row rejection frame with the canonical reason column.

    A bare ``pl.DataFrame()`` is 0x0; adding ``pl.lit(None)`` to it
    broadcasts to 1 row, which would create phantom rejection rows.
    """
    return pl.DataFrame({"_validation_errors": pl.Series([], dtype=pl.String)})


@pytest.fixture()
def logger() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def customers_df() -> pl.DataFrame:
    return _df(
        [
            {"customer_id": "c1", "name": "Acme1"},
            {"customer_id": "c2", "name": "Acme2"},
        ]
    )


@pytest.fixture()
def orders_df() -> pl.DataFrame:
    return _df(
        [
            {
                "order_id": "o1",
                "customer_id": "C1",
                "ordered_at": "2026-10-01T10:00:00Z",
                "status": "SHIPPED",
                "cancelled_at": None,
            },
            {
                "order_id": "o2",
                "customer_id": "C2",
                "ordered_at": "2026-10-01T10:00:00Z",
                "status": "SHIPPED",
                "cancelled_at": None,
            },
        ]
    )


@pytest.fixture()
def order_lines_df() -> pl.DataFrame:
    return _df(
        [
            {
                "order_line_id": "l1",
                "order_id": "o1",
                "product_id": "P001",
                "quantity": "2",
                "unit_price_amount": "10.00",
                "unit_price_currency": "USD",
            },
            {
                "order_line_id": "l2",
                "order_id": "o2",
                "product_id": "P001",
                "quantity": "2",
                "unit_price_amount": "10.00",
                "unit_price_currency": "USD",
            },
        ]
    )


@pytest.fixture()
def batch(customers_df, orders_df, order_lines_df) -> CustomerOrdersBatch:
    return CustomerOrdersBatch(
        customers=customers_df,
        orders=orders_df,
        order_lines=order_lines_df,
    )


@pytest.fixture()
def validators() -> dict[str, MagicMock]:
    """Create mock validators with pass-through default behaviour.

    Every validator returns its input as `valid` and an empty DataFrame as
    `rejected`, so by default nothing is rejected anywhere.
    """
    schema_validator = MagicMock(name="schema_validator")
    missing_value_validator = MagicMock(name="missing_value_validator")
    duplicate_detector = MagicMock(name="duplicate_detector")
    business_validator = MagicMock(name="business_validator")
    cross_file_validator = MagicMock(name="cross_file_validator")

    for mock in (missing_value_validator, business_validator):
        mock.validate.side_effect = lambda data, dataset_name: ValidationResult(
            valid=data, rejected=_empty_rejected()
        )
    schema_validator.validate.side_effect = lambda data, expected_schema, dataset_name: (
        data
    )
    duplicate_detector.detect.side_effect = lambda data, dataset_name: ValidationResult(
        valid=data, rejected=_empty_rejected()
    )

    cross_file_validator.validate.side_effect = lambda customers, orders, order_lines: (
        CustomerOrdersCrossFileValidationResult(
            orders=ValidationResult(valid=orders, rejected=_empty_rejected()),
            order_lines=ValidationResult(valid=order_lines, rejected=_empty_rejected()),
        )
    )

    return {
        "schema_validator": schema_validator,
        "missing_value_validator": missing_value_validator,
        "duplicate_detector": duplicate_detector,
        "business_validator": business_validator,
        "cross_file_validator": cross_file_validator,
    }


@pytest.fixture()
def service(validators, logger) -> CustomerOrdersValidationService:
    return CustomerOrdersValidationService(
        logger=logger,
        **validators,
    )


class TestSchemaValidation:
    def test_schema_validator_called_for_all_datasets(self, service, validators, batch):
        service.validate(batch)

        schema = validators["schema_validator"].validate
        assert schema.call_count == 3
        schema.assert_has_calls(
            [
                call(batch.customers, CUSTOMER_SCHEMA, "customers"),
                call(batch.orders, ORDER_SCHEMA, "orders"),
                call(batch.order_lines, ORDER_LINE_SCHEMA, "order_lines"),
            ],
            any_order=False,
        )

    def test_per_dataset_validators_called_in_order(self, service, validators, batch):
        service.validate(batch)

        missing = validators["missing_value_validator"].validate
        duplicate = validators["duplicate_detector"].detect
        business = validators["business_validator"].validate

        for name in ("customers", "orders", "order_lines"):
            data = getattr(batch, name)

            missing_calls = [
                c
                for c in missing.call_args_list
                if c.args[0] is data and c.args[1] == name
            ]
            duplicate_calls = [
                c
                for c in duplicate.call_args_list
                if c.args[0] is data and c.args[1] == name
            ]
            business_calls = [
                c
                for c in business.call_args_list
                if c.args[0] is data and c.args[1] == name
            ]
            assert len(missing_calls) == 1
            assert len(duplicate_calls) == 1
            assert len(business_calls) == 1

        missing_order = [c.args[1] for c in missing.call_args_list]
        assert missing_order == ["customers", "orders", "order_lines"]


class TestCrossFileValidation:
    def test_cross_file_validator_receives_business_valid_records(
        self, service, validators, batch
    ):
        def business_validate(data, name):
            return ValidationResult(valid=data.head(1), rejected=data.tail(1))

        validators["business_validator"].validate.side_effect = business_validate

        service.validate(batch)

        cross = validators["cross_file_validator"]
        cross.validate.assert_called_once()
        kwargs = cross.validate.call_args.kwargs

        assert kwargs["customers"].equals(batch.customers.head(1))
        assert kwargs["orders"].equals(batch.orders.head(1))
        assert kwargs["order_lines"].equals(batch.order_lines.head(1))

    def test_cross_file_rejections_are_appended_to_rejected(
        self, service, validators, batch
    ):
        rejected_orders = _df(
            [{"order_id": "bad", "_cross_file_errors": "orphan order"}]
        )
        validators["cross_file_validator"].validate.side_effect = (
            lambda customers, orders, order_lines: MagicMock(
                orders=ValidationResult(
                    valid=orders.filter(pl.col("order_id") != "bad"),
                    rejected=rejected_orders,
                ),
                order_lines=ValidationResult(
                    valid=order_lines, rejected=_empty_rejected()
                ),
            )
        )
        batch = CustomerOrdersBatch(
            customers=batch.customers,
            orders=_df([{"order_id": "bad"}]),
            order_lines=batch.order_lines,
        )

        result = service.validate(batch)

        assert result.orders.valid.is_empty()
        assert result.orders.rejected.height == 1
        row = result.orders.rejected.row(0, named=True)
        assert row["order_id"] == "bad"
        assert row["_validation_errors"] == "orphan order"


class TestResultAssembly:
    def test_valid_records_flow_through_when_nothing_rejected(self, service, batch):
        result = service.validate(batch)

        assert result.customers.valid.equals(batch.customers)
        assert result.orders.valid.equals(batch.orders)
        assert result.order_lines.valid.equals(batch.order_lines)
        assert result.customers.rejected.is_empty()
        assert result.orders.rejected.is_empty()
        assert result.order_lines.rejected.is_empty()

    def test_rejected_rows_from_all_stages_are_combined(
        self, service, validators, batch
    ):
        validators["missing_value_validator"].validate.side_effect = lambda data, name: (
            ValidationResult(
                valid=data.head(1),
                rejected=data.tail(1).with_columns(
                    pl.lit("missing").alias("_validation_errors")
                ),
            )
        )
        validators["duplicate_detector"].detect.side_effect = lambda data, name: (
            ValidationResult(
                valid=data,
                rejected=pl.DataFrame(
                    {"customer_id": ["dup"], "_duplicate_errors": ["dup"]}
                ),
            )
        )

        result = service.validate(batch)

        assert result.customers.rejected.height == 2
        reasons = set(result.customers.rejected["_validation_errors"].to_list())
        assert reasons == {"missing", "dup"}
        assert result.customers.valid.height == 1

    def test_logs_summary_counts(self, logger, service, batch):
        service.validate(batch)

        logger.info.assert_any_call(
            "Customer-orders validation completed. "
            "Customers: %d valid, %d rejected; "
            "orders: %d valid, %d rejected; "
            "order lines: %d valid, %d rejected.",
            2,
            0,
            2,
            0,
            2,
            0,
        )


class TestNormalizeRejections:
    def test_adds_empty_reason_column_when_missing(self):
        df = _df([{"customer_id": "c1"}])

        result = CustomerOrdersValidationService._normalize_rejections(df)

        assert "_validation_errors" in result.columns
        assert result["_validation_errors"].to_list() == [None]

    def test_renames_reason_column_to_canonical_name(self):
        df = _df([{"customer_id": "c1", "_duplicate_errors": "dup"}])

        result = CustomerOrdersValidationService._normalize_rejections(df)

        assert "_duplicate_errors" not in result.columns
        assert result["_validation_errors"].to_list() == ["dup"]

    def test_drops_non_canonical_reason_columns(self):
        df = _df(
            [
                {
                    "customer_id": "c1",
                    "_duplicate_errors": "dup",
                    "_cross_file_errors": "x",
                }
            ]
        )

        result = CustomerOrdersValidationService._normalize_rejections(df)

        assert result.columns == ["customer_id", "_validation_errors"]
        assert result["_validation_errors"].to_list() == ["dup"]


class TestCombineRejections:
    def test_concatenates_frames_with_diagonal_schema(self):
        frames = [
            _df([{"customer_id": "c1", "_validation_errors": "missing"}]),
            _df([{"email": "x@y.z", "_duplicate_errors": "dup"}]),
        ]

        combined = CustomerOrdersValidationService._combine_rejections(frames)

        assert combined.height == 2
        assert "_validation_errors" in combined.columns

    def test_raises_on_empty_frame_list(self):
        with pytest.raises(ValueError, match="At least one"):
            CustomerOrdersValidationService._combine_rejections([])
