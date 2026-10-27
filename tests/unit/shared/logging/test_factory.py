import logging

import pytest

from agpp.shared.logging.factory import get_pipeline_logger


def test_pipeline_logger_is_named_after_the_pipeline() -> None:
    logger = get_pipeline_logger("supplier_product", "run-1")

    assert logger.logger.name == "agpp.pipelines.supplier_product"


def test_records_carry_pipeline_and_run_id(caplog: pytest.LogCaptureFixture) -> None:
    logger = get_pipeline_logger("supplier_product", "run-1")

    with caplog.at_level(logging.INFO, logger="agpp.pipelines.supplier_product"):
        logger.info("started")

    fields = caplog.records[0].__dict__
    assert fields["pipeline"] == "supplier_product"
    assert fields["run_id"] == "run-1"


def test_per_call_extra_is_merged_with_context(caplog: pytest.LogCaptureFixture) -> None:
    logger = get_pipeline_logger("supplier_product", "run-1")

    with caplog.at_level(logging.INFO, logger="agpp.pipelines.supplier_product"):
        logger.info("extracted", extra={"rows": 5})

    fields = caplog.records[0].__dict__
    assert fields["rows"] == 5
    assert fields["run_id"] == "run-1"
