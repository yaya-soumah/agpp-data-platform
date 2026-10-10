import polars as pl

CUSTOMER_SCHEMA = {
    "customer_id": pl.String,
    "name": pl.String,
}

ORDER_SCHEMA = {
    "order_id": pl.String,
    "customer_id": pl.String,
    "ordered_at": pl.String,
    "status": pl.String,
    "cancelled_at": pl.String,
}

ORDER_LINE_SCHEMA = {
    "order_line_id": pl.String,
    "order_id": pl.String,
    "product_id": pl.String,
    "quantity": pl.String,
    "unit_price_amount": pl.String,
    "unit_price_currency": pl.String,
}
