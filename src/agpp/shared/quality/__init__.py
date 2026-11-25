"""Configurable data-quality checks over the warehouse (ADR-0020)."""

from agpp.shared.quality.models import CheckStatus, Comparison, QualityCheck, QualityConfig
from agpp.shared.quality.runner import CheckResult, evaluate, measure, run_checks
from agpp.shared.quality.service import QualitySummary, run_quality_checks
from agpp.shared.quality.store import store_results

__all__ = [
    "CheckResult",
    "CheckStatus",
    "Comparison",
    "QualityCheck",
    "QualityConfig",
    "QualitySummary",
    "evaluate",
    "measure",
    "run_checks",
    "run_quality_checks",
    "store_results",
]
