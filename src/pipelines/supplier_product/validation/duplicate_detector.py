import polars as pl

from .result import ValidationResult

_DUPLICATE_ERRORS_COLUMN = "_duplicate_errors"
_DUPLICATE_MESSAGE = "supplier_product_id is duplicated"


class DefaultSupplierProductDuplicateDetector:
    """Detect duplicate supplier-product records."""

    def detect(self,data: pl.DataFrame) -> ValidationResult:
        duplicate_ids = (
            data.group_by("supplier_product_id")
            .len()
            .filter(pl.col("len") > 1)
            .select("supplier_product_id")
        )

        rejected = (
            data.join(
                duplicate_ids,
                on="supplier_product_id",
                how="semi",
            )
            .with_columns(
                pl.lit(_DUPLICATE_MESSAGE).alias(_DUPLICATE_ERRORS_COLUMN)
            )
        )

        valid = data.join(
            duplicate_ids,
            on="supplier_product_id",
            how="anti",
        )

        return ValidationResult(
            valid=valid,
            rejected=rejected,
        )