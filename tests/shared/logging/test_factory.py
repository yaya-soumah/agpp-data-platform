import logging

from src.shared.logging import get_logger


def test_get_logger_returns_logger():
    logger = get_logger("agpp.test")

    assert isinstance(logger, logging.Logger)


def test_get_logger_returns_requested_name():
    logger = get_logger("agpp.pipeline.supplier_product")

    assert logger.name == "agpp.pipeline.supplier_product"