from decimal import Decimal
from typing import Protocol

import polars as pl
from src.shared.currency import Currency


class ExchangeRateProvider(Protocol):
    """Provide exchange rates between supported currencies."""

    async def get_rate(
        self,
        from_currency: Currency,
        to_currency: Currency,
    ) -> Decimal:
        """Return the target-currency value of one unit of source currency."""

        ...


class SupplierProductCurrencyConverter(Protocol):
    """Contract for supplier-product currency conversion."""

    async def convert(self, data: pl.DataFrame) -> pl.DataFrame:
        """Convert supplier-product prices to the canonical currency."""

        ...
