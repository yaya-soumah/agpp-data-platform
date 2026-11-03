from agpp.pipelines.supplier_product.validation.result import (
    RejectedRecord,
    RejectionStage,
    ValidationResult,
)


def _rejected(line: int, stage: RejectionStage = RejectionStage.PARSING) -> RejectedRecord:
    return RejectedRecord("SUP-001", line, stage, ("unit_price: bad",), {"unit_price": "x"})


def _result(rows_read: int, rejected: tuple[RejectedRecord, ...]) -> ValidationResult:
    return ValidationResult("SUP-001", rows_read, (), rejected)


def test_reject_ratio_is_rejected_over_rows_read() -> None:
    result = _result(10, (_rejected(2), _rejected(3)))

    assert result.reject_ratio == 0.2


def test_a_file_without_data_rows_has_a_zero_ratio() -> None:
    assert _result(0, ()).reject_ratio == 0.0


def test_rejections_are_counted_per_stage() -> None:
    result = _result(
        10,
        (
            _rejected(2),
            _rejected(3),
            _rejected(4, RejectionStage.BUSINESS),
            _rejected(5, RejectionStage.DUPLICATE),
        ),
    )

    assert result.rejected_by(RejectionStage.PARSING) == 2
    assert result.rejected_by(RejectionStage.BUSINESS) == 1
    assert result.rejected_by(RejectionStage.DUPLICATE) == 1


def test_ignored_columns_default_to_none() -> None:
    assert _result(1, ()).ignored_columns == ()
