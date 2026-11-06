"""Loading stage: write each supplier atomically and independently (ADR-0014)."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from agpp.pipelines.supplier_product import PIPELINE_NAME
from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.loading.loader import LoadResult, load_supplier
from agpp.pipelines.supplier_product.transformation import SupplierTransformation
from agpp.pipelines.supplier_product.validation import SupplierValidation
from agpp.shared.database import Pool
from agpp.shared.exceptions import AgppError, LoadingError
from agpp.shared.logging import get_pipeline_logger
from agpp.shared.resilience.retry import RetryPolicy


@dataclass(frozen=True)
class SupplierLoad:
    """The outcome for one supplier: what was loaded, or the error that stopped it."""

    supplier_id: str
    result: LoadResult | None = None
    error: AgppError | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def load_all(
    pool: Pool,
    config: SupplierProductConfig,
    transformations: Sequence[SupplierTransformation],
    validations: Sequence[SupplierValidation],
    *,
    run_id: str,
    supplier_loader: Callable[..., LoadResult] = load_supplier,
    sleep: Callable[[float], None] = time.sleep,
) -> list[SupplierLoad]:
    """Load every transformed supplier independently.

    A supplier whose earlier stage failed is carried through with that error.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    policy = RetryPolicy(
        max_attempts=config.loading.max_attempts,
        initial_delay=config.loading.initial_delay_seconds,
    )
    results = {v.supplier_id: v.result for v in validations if v.result is not None}
    log.info("Loading started", extra={"suppliers": len(transformations)})

    outcomes: list[SupplierLoad] = []
    for transformation in transformations:
        supplier_id = transformation.supplier_id
        if transformation.batch is None:
            outcomes.append(SupplierLoad(supplier_id, error=transformation.error))
            continue
        try:
            validation = results.get(supplier_id)
            if validation is None:
                raise LoadingError(
                    "No validation result for the supplier", context={"supplier_id": supplier_id}
                )
            loaded = supplier_loader(
                pool,
                run_id=run_id,
                batch=transformation.batch,
                validation=validation,
                retry_policy=policy,
                sleep=sleep,
            )
        except AgppError as error:
            log.exception(
                "Supplier loading failed",
                extra={
                    "supplier_id": supplier_id,
                    "stage": error.stage,
                    "error_context": error.context,
                },
            )
            outcomes.append(SupplierLoad(supplier_id, error=error))
            continue
        log.info(
            "Supplier loaded",
            extra={
                "supplier_id": supplier_id,
                "products": loaded.products_attempted,
                "written": loaded.products_written,
                "unchanged": loaded.products_unchanged,
                "rejects_stored": loaded.rejects_stored,
            },
        )
        outcomes.append(SupplierLoad(supplier_id, result=loaded))

    failed = sum(1 for outcome in outcomes if not outcome.succeeded)
    log.info("Loading finished", extra={"succeeded": len(outcomes) - failed, "failed": failed})
    return outcomes
