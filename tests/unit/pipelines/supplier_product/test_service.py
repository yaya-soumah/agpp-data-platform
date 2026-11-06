from agpp.pipelines.supplier_product.loading import RunStatus
from agpp.pipelines.supplier_product.service import SupplierOutcome, _status
from agpp.shared.exceptions import ExtractionError


def _ok(supplier_id: str) -> SupplierOutcome:
    return SupplierOutcome(supplier_id)


def _failed(supplier_id: str) -> SupplierOutcome:
    return SupplierOutcome(supplier_id, error=ExtractionError("x"))


def test_the_run_succeeds_when_every_supplier_loaded() -> None:
    assert _status([_ok("SUP-001"), _ok("SUP-002")]) is RunStatus.SUCCEEDED


def test_the_run_fails_when_no_supplier_loaded() -> None:
    assert _status([_failed("SUP-001"), _failed("SUP-002")]) is RunStatus.FAILED


def test_the_run_is_partial_when_some_suppliers_failed() -> None:
    assert _status([_ok("SUP-001"), _failed("SUP-002")]) is RunStatus.PARTIAL
