from collections.abc import Iterator
from pathlib import Path

import pytest

from agpp.pipelines.supplier_product.config import SupplierConfig
from agpp.pipelines.supplier_product.extraction import (
    ExtractionResult,
    create_extractor,
    factory,
    register_extractor,
)
from agpp.pipelines.supplier_product.extraction.csv_extractor import CsvExtractor
from agpp.shared.exceptions import UnsupportedSourceError


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    saved = dict(factory._BUILDERS)
    yield
    factory._BUILDERS.clear()
    factory._BUILDERS.update(saved)


class FakeExtractor:
    def __init__(self, supplier: SupplierConfig) -> None:
        self.supplier = supplier

    def extract(self) -> ExtractionResult:
        return ExtractionResult(self.supplier.supplier_id, "fake", (), ())


def _supplier(tmp_path: Path) -> SupplierConfig:
    return SupplierConfig.model_validate(
        {
            "supplier_id": "SUP-001",
            "name": "One",
            "country": "LU",
            "source": {"type": "csv", "path": str(tmp_path / "one.csv")},
        }
    )


def _with_source_type(supplier: SupplierConfig, source_type: str) -> SupplierConfig:
    source = supplier.source.model_copy(update={"type": source_type})
    return supplier.model_copy(update={"source": source})


def test_csv_sources_get_the_csv_extractor(tmp_path: Path) -> None:
    assert isinstance(create_extractor(_supplier(tmp_path)), CsvExtractor)


def test_unknown_source_types_are_rejected(tmp_path: Path) -> None:
    supplier = _with_source_type(_supplier(tmp_path), "ftp")

    with pytest.raises(UnsupportedSourceError) as info:
        create_extractor(supplier)

    assert info.value.context == {"supplier_id": "SUP-001", "source_type": "ftp"}


def test_new_source_types_can_be_registered(tmp_path: Path) -> None:
    register_extractor("ftp", FakeExtractor)
    supplier = _with_source_type(_supplier(tmp_path), "ftp")

    extractor = create_extractor(supplier)

    assert isinstance(extractor, FakeExtractor)
    assert extractor.extract().supplier_id == "SUP-001"
