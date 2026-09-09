import polars as pl

_PRICE_AMOUNT_DTYPE = pl.Decimal(precision=38, scale=6)
_QUANTITY_DTYPE = pl.Decimal(precision=38, scale=6)


class DefaultSupplierProductTransformer:
    """Transform validated supplier-product data into canonical representation."""

    def transform(self, data: pl.DataFrame) -> pl.DataFrame:
        return data.with_columns(
            pl.col("price").cast(_PRICE_AMOUNT_DTYPE).alias("price_amount"),
            pl.col("currency").alias("price_currency"),
            pl.col("minimum_order_quantity")
            .cast(_QUANTITY_DTYPE)
            .alias("minimum_order_quantity"),
        ).drop("price", "currency")
