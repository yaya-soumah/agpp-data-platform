import polars as pl
from src.pipelines.supplier_product.validation import (
    DefaultSupplierProductDuplicateDetector,
)


def test_unique_supplier_product_ids_are_valid() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001", "SP-002"],
            "supplier_id": ["SUP-001", "SUP-001"],
            "supplier_sku": ["ABC-500", "ABC-750"],
        }
    )

    result = DefaultSupplierProductDuplicateDetector().detect(data)

    assert result.valid.equals(data)
    assert result.rejected.height == 0


def test_duplicate_supplier_product_ids_are_all_rejected() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001", "SP-001"],
            "supplier_id": ["SUP-001", "SUP-001"],
            "supplier_sku": ["ABC-500", "ABC-500"],
        }
    )

    result = DefaultSupplierProductDuplicateDetector().detect(data)

    assert result.valid.height == 0
    assert result.rejected.height == 2


def test_all_occurrences_of_duplicate_id_are_rejected() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001", "SP-001", "SP-001"],
            "supplier_id": ["SUP-001", "SUP-001", "SUP-001"],
            "supplier_sku": ["ABC-500", "ABC-500", "ABC-500"],
        }
    )

    result = DefaultSupplierProductDuplicateDetector().detect(data)

    assert result.valid.height == 0
    assert result.rejected.height == 3


def test_multiple_duplicate_groups_are_rejected() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": [
                "SP-001",
                "SP-001",
                "SP-002",
                "SP-002",
                "SP-003",
            ],
            "supplier_id": [
                "SUP-001",
                "SUP-001",
                "SUP-002",
                "SUP-002",
                "SUP-003",
            ],
        }
    )

    result = DefaultSupplierProductDuplicateDetector().detect(data)

    assert result.valid["supplier_product_id"].to_list() == ["SP-003"]
    assert result.rejected["supplier_product_id"].to_list() == [
        "SP-001",
        "SP-001",
        "SP-002",
        "SP-002",
    ]


def test_unique_rows_are_preserved_unchanged() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001", "SP-002"],
            "supplier_id": ["SUP-001", "SUP-002"],
            "supplier_sku": ["ABC-500", "XYZ-100"],
        }
    )

    result = DefaultSupplierProductDuplicateDetector().detect(data)

    assert result.valid.equals(data)
    assert result.valid.columns == data.columns


def test_rejected_rows_preserve_origin_columns_and_add_error() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001", "SP-001"],
            "supplier_id": ["SUP-001", "SUP-001"],
            "supplier_sku": ["ABC-500", "ABC-500"],
        }
    )

    result = DefaultSupplierProductDuplicateDetector().detect(data)

    assert result.rejected.columns == [
        "supplier_product_id",
        "supplier_id",
        "supplier_sku",
        "_duplicate_errors",
    ]
    assert result.rejected["_duplicate_errors"].to_list() == [
        "supplier_product_id is duplicated",
        "supplier_product_id is duplicated",
    ]


def test_empty_dataframe_returns_no_valid_or_rejected_rows() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": pl.Series([], dtype=pl.String),
            "supplier_id": pl.Series([], dtype=pl.String),
        }
    )

    result = DefaultSupplierProductDuplicateDetector().detect(data)

    assert result.valid.height == 0
    assert result.rejected.height == 0
    assert result.valid.columns == data.columns
