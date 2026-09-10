from decimal import Decimal

import polars as pl
import pytest
from src.pipelines.supplier_product.currency_conversion import (
    DefaultSupplierProductCurrencyConverter,
)
from src.shared.currency import Currency


class FakeExchangeRateProvider:
    def __init__(self, rates: dict[tuple[Currency, Currency], Decimal]) -> None:
        self.rates = rates
        self.calls: list[tuple[Currency, Currency]] = []

    async def get_rate(
        self,
        from_currency: Currency,
        to_currency: Currency,
    ) -> Decimal:
        self.calls.append((from_currency, to_currency))
        return self.rates[(from_currency, to_currency)]


@pytest.mark.asyncio
async def test_converts_foreign_currency_to_eur() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001"],
            "supplier_id": ["SUP-001"],
            "supplier_sku": ["ABC-500"],
            "name": ["Bottle"],
            "description": [None],
            "price_amount": [Decimal("8.50")],
            "price_currency": ["USD"],
            "minimum_order_quantity": [Decimal("100")],
            "lead_time_days": [7],
        }
    )

    provider = FakeExchangeRateProvider(
        {
            (Currency.USD, Currency.EUR): Decimal("0.85"),
        }
    )

    converter = DefaultSupplierProductCurrencyConverter(provider)

    result = await converter.convert(data)

    assert result["price_amount"].to_list() == [Decimal("8.50")]
    assert result["price_currency"].to_list() == ["USD"]
    assert result["price_amount_eur"].to_list() == [Decimal("7.225000")]

    assert provider.calls == [
        (Currency.USD, Currency.EUR),
    ]


@pytest.mark.asyncio
async def test_eur_price_does_not_call_exchange_rate_provider() -> None:
    data = pl.DataFrame(
        {
            "price_amount": [Decimal("12.50")],
            "price_currency": ["EUR"],
        }
    )

    provider = FakeExchangeRateProvider({})

    converter = DefaultSupplierProductCurrencyConverter(provider)

    result = await converter.convert(data)

    assert result["price_amount_eur"].to_list() == [Decimal("12.500000")]
    assert provider.calls == []


@pytest.mark.asyncio
async def test_fetches_one_rate_per_unique_foreign_currency() -> None:
    data = pl.DataFrame(
        {
            "price_amount": [
                Decimal("10"),
                Decimal("20"),
                Decimal("30"),
            ],
            "price_currency": [
                "USD",
                "USD",
                "CNY",
            ],
        }
    )

    provider = FakeExchangeRateProvider(
        {
            (Currency.USD, Currency.EUR): Decimal("0.85"),
            (Currency.CNY, Currency.EUR): Decimal("0.13"),
        }
    )

    converter = DefaultSupplierProductCurrencyConverter(provider)

    result = await converter.convert(data)

    assert result["price_amount_eur"].to_list() == [
        Decimal("8.500000"),
        Decimal("17.000000"),
        Decimal("3.900000"),
    ]

    assert sorted(provider.calls, key=lambda call: call[0].value) == [
        (Currency.CNY, Currency.EUR),
        (Currency.USD, Currency.EUR),
    ]


@pytest.mark.asyncio
async def test_null_price_remains_null() -> None:
    data = pl.DataFrame(
        {
            "price_amount": [None],
            "price_currency": [None],
        },
        schema={
            "price_amount": pl.Decimal(38, 6),
            "price_currency": pl.String,
        },
    )

    provider = FakeExchangeRateProvider({})

    converter = DefaultSupplierProductCurrencyConverter(provider)

    result = await converter.convert(data)

    assert result["price_amount_eur"].to_list() == [None]
    assert provider.calls == []
