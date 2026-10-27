"""Logger creation helpers."""

import logging
from collections.abc import MutableMapping
from typing import Any


class ContextLogger(logging.LoggerAdapter[logging.Logger]):
    """Adds fixed context fields (pipeline, run_id) to every record."""

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        extra: dict[str, Any] = dict(self.extra or {})
        extra.update(kwargs.get("extra", {}))
        kwargs["extra"] = extra
        return msg, kwargs


def get_pipeline_logger(pipeline: str, run_id: str) -> ContextLogger:
    """Return the logger for one pipeline run, named ``agpp.pipelines.<pipeline>``."""
    logger = logging.getLogger(f"agpp.pipelines.{pipeline}")
    return ContextLogger(logger, {"pipeline": pipeline, "run_id": run_id})
