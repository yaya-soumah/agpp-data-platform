import polars as pl

SUPPLIER_PRODUCT_SCHEMA = {
    "supplier_product_id": pl.String,
    "supplier_id": pl.String,
    "supplier_sku": pl.String,
    "name": pl.String,
    "description": pl.String,
    "price": pl.String,
    "currency": pl.String,
    "minimum_order_quantity": pl.Int64,
    "lead_time_days": pl.Int64,
}
