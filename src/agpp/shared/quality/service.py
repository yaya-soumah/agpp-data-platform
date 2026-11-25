"""Run the configured data-quality checks once and record the outcome (ADR-0020)."""

from dataclasses import dataclass

from agpp.shared.database import Pool
from agpp.shared.logging import get_pipeline_logger
from agpp.shared.quality.models import CheckStatus, QualityConfig
from agpp.shared.quality.runner import CheckResult, run_checks
from agpp.shared.quality.store import store_results

PIPELINE_NAME = "data_quality"


@dataclass(frozen=True)
class QualitySummary:
    """The results of one run of the checks."""

    run_id: str
    results: tuple[CheckResult, ...]

    def count(self, status: CheckStatus) -> int:
        return sum(1 for result in self.results if result.status is status)

    @property
    def failed(self) -> bool:
        """True when any check failed or could not run."""
        return self.count(CheckStatus.FAIL) + self.count(CheckStatus.ERROR) > 0


def run_quality_checks(pool: Pool, config: QualityConfig, *, run_id: str) -> QualitySummary:
    """Run every check, store the results and log each outcome."""
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    results = run_checks(pool, config)
    store_results(pool, run_id, results)

    for result in results:
        extra = {
            "check": result.check.name,
            "status": result.status.value,
            "value": result.value,
            "detail": result.message,
        }
        if result.status is CheckStatus.WARN:
            log.warning("Quality check warning", extra=extra)
        elif result.status in (CheckStatus.FAIL, CheckStatus.ERROR):
            log.error("Quality check failed", extra=extra)
        else:
            log.info("Quality check", extra=extra)

    summary = QualitySummary(run_id, results)
    log.info(
        "Data quality checked",
        extra={status.value: summary.count(status) for status in CheckStatus},
    )
    return summary
