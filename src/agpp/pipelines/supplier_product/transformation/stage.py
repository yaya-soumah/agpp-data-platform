"""Transformation stage: map each validated supplier to warehouse rows (ADR-0013)."""

from collections.abc import Sequence
from dataclasses import dataclass

from agpp.pipelines.supplier_product import PIPELINE_NAME
from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.transformation.rows import TransformedBatch
from agpp.pipelines.supplier_product.transformation.transformer import transform_supplier
from agpp.pipelines.supplier_product.validation import SupplierValidation
from agpp.shared.exceptions import AgppError, TransformationError
from agpp.shared.logging import get_pipeline_logger


@dataclass(frozen=True)
class SupplierTransformation:
    """The outcome for one supplier: rows to load, or the error that stopped it."""

    supplier_id: str
    batch: TransformedBatch | None = None
    error: AgppError | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def transform_all(
    config: SupplierProductConfig,
    validations: Sequence[SupplierValidation],
    *,
    run_id: str,
) -> list[SupplierTransformation]:
    """Transform every validated supplier independently.

    A supplier whose earlier stage failed is carried through with that error.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    suppliers = {supplier.supplier_id: supplier for supplier in config.suppliers}
    log.info("Transformation started", extra={"suppliers": len(validations)})

    outcomes: list[SupplierTransformation] = []
    for validation in validations:
        if validation.result is None:
            outcomes.append(SupplierTransformation(validation.supplier_id, error=validation.error))
            continue
        try:
            supplier = suppliers.get(validation.supplier_id)
            if supplier is None:
                raise TransformationError(
                    "Supplier is not in the pipeline configuration",
                    context={"supplier_id": validation.supplier_id},
                )
            batch = transform_supplier(supplier, validation.result.valid)
        except AgppError as error:
            log.exception(
                "Supplier transformation failed",
                extra={
                    "supplier_id": validation.supplier_id,
                    "stage": error.stage,
                    "error_context": error.context,
                },
            )
            outcomes.append(SupplierTransformation(validation.supplier_id, error=error))
            continue
        log.info(
            "Supplier transformed",
            extra={"supplier_id": validation.supplier_id, "products": len(batch.products)},
        )
        outcomes.append(SupplierTransformation(validation.supplier_id, batch=batch))

    failed = sum(1 for outcome in outcomes if not outcome.succeeded)
    log.info(
        "Transformation finished", extra={"succeeded": len(outcomes) - failed, "failed": failed}
    )
    return outcomes
