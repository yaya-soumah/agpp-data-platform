import asyncio
from decimal import Decimal

import polars as pl
from src.shared.currency import Currency

from .base import ExchangeRateProvider

CANONICAL_CURRENCY = Currency.EUR
_DECIMAL_DTYPE = pl.Decimal(precision=38, scale=6)


class DefaultSupplierProductCurrencyConverter:
    """Convert supplier-product prices to canonical currency."""

    def __init__(self, exchange_rate: ExchangeRateProvider) -> None:
        self._exchange_rate_provider = exchange_rate

    async def convert(self, data: pl.DataFrame) -> pl.DataFrame:
        currencies = (
            data.select(pl.col("price_currency").drop_nulls().unique())
            .to_series()
            .to_list()
        )

        rates = await self._get_exchange_rates(currencies)

        return self._apply_conversion(data, rates)

    async def _get_exchange_rates(
        self,
        currencies: list[str],
    ) -> dict[str, Decimal]:
        source_currencies = [
            Currency(currency_value)
            for currency_value in currencies
            if Currency(currency_value) != CANONICAL_CURRENCY
        ]

        rates = await asyncio.gather(
            *(
                self._exchange_rate_provider.get_rate(
                    currency,
                    CANONICAL_CURRENCY,
                )
                for currency in source_currencies
            )
        )
        return {
            CANONICAL_CURRENCY.value: Decimal("1"),
            **dict(
                zip(
                    (currency.value for currency in source_currencies),
                    rates,
                    strict=True,
                )
            ),
        }

    def _apply_conversion(
        self,
        data: pl.DataFrame,
        rates: dict[str, Decimal],
    ) -> pl.DataFrame:
        rate_frame = pl.DataFrame(
            {
                "price_currency": list(rates.keys()),
                "_exchange_rate": list(rates.values()),
            },
            schema={
                "price_currency": pl.String,
                "_exchange_rate": _DECIMAL_DTYPE,
            },
        )

        return (
            data.join(
                rate_frame,
                on="price_currency",
                how="left",
            )
            .with_columns(
                pl.when(pl.col("price_amount").is_null())
                .then(None)
                .otherwise((pl.col("price_amount") * pl.col("_exchange_rate")).round(6))
                .cast(_DECIMAL_DTYPE)
                .alias("price_amount_eur")
            )
            .drop("_exchange_rate")
        )
