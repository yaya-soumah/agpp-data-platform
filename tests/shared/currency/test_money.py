from decimal import Decimal
from dataclasses import FrozenInstanceError

import pytest

from src.shared.currency import (
    Currency,
    CurrencyMismatchError,
    InvalidExchangeRateError,
    InvalidMoneyAmountError,
    Money,
)

class TestMoneyCreation:
    def test_creates_money_from_decimal(self):
        money = Money(
            amount=Decimal('100.50'),
            currency=Currency.EUR
        )

        assert money.amount == Decimal('100.50')
        assert money.currency == Currency.EUR

    def test_from_value_accepts_string(self):
        money = Money.from_value(
            '100.50',
            Currency.EUR,
        )

        assert money.amount == Decimal('100.50')
        assert money.currency == Currency.EUR

    def test_from_value_accepts_integer(self):
        money = Money.from_value(
            100,
            Currency.EUR
        )

        assert money.amount == Decimal('100')

    def test_from_value_accepts_decimal(self):
        money = Money(
            Decimal('100.50'),
            Currency.EUR
        )

        assert money.amount == Decimal('100.50')

    def test_reject_non_decimal_amount_in_constructor(self):
        with pytest.raises(InvalidMoneyAmountError):
            Money(
                amount=100.50,
                currency=Currency.EUR,
            )

    @pytest.mark.parametrize(
        "value",
        [
            "not-a-number",
            "",
            "NaN",
            "Infinity",
            "-Infinity"
        ]
    )
    def test_from_value_rejects_invalid_amounts(self,value):
        with pytest.raises(InvalidMoneyAmountError):
            Money.from_value(
                value, Currency.EUR
            )
    def test_rejects_invslid_currency_type(self):
        with pytest.raises(TypeError):
            Money(
                amount=Decimal('100'),
                currency='EUR'
            )
class TestMoneyArthimetic:
    def test_adds_same_currency(self):
        first =Money.from_value('100.25', Currency.EUR)
        second =Money.from_value('50.75', Currency.EUR)

        result = first.add(second)

        assert isinstance(result,Money)
        assert result.amount == Decimal('151')
        assert result.currency == Currency.EUR

    def test_subtracts_same_currency(self):
        first =Money.from_value('100.25', Currency.EUR)
        second =Money.from_value('40.25', Currency.EUR)

        result = first.subtract(second)

        assert isinstance(result,Money)
        assert result.amount == Decimal('60')
        assert result.currency == Currency.EUR

    def test_rejects_addition_of_different_currencies(self):
        eur = Money.from_value('100', Currency.EUR)
        usd = Money.from_value('100', Currency.USD)

        with pytest.raises(CurrencyMismatchError):
            eur.add(usd)
            
    def test_rejects_subtracrion_of_different_currencies(self):
        eur = Money.from_value('100', Currency.EUR)
        usd = Money.from_value('100', Currency.USD)

        with pytest.raises(CurrencyMismatchError):
            eur.subtract(usd)

    def test_multiplies_by_decimal(self):
        money = Money.from_value('100', Currency.EUR)

        result = money.multiply('0.15')

        assert isinstance(result, Money)
        assert result.amount == Decimal('15.00')
        assert result.currency == Currency.EUR

    def test_multiplies_by_integer(self):
        money = Money.from_value('25', Currency.EUR)

        result = money.multiply(4)

        assert isinstance(result, Money)
        assert result.amount == Decimal('100.00')
        assert result.currency == Currency.EUR

    def test_divides_by_integer(self):
        money = Money.from_value('100', Currency.EUR)

        result = money.divide(25)

        assert isinstance(result, Money)
        assert result.amount == Decimal('4.00')
        assert result.currency == Currency.EUR

    def test_divides_by_decimal(self):
        money = Money.from_value('100', Currency.EUR)

        result = money.divide('2.5')

        assert isinstance(result, Money)
        assert result.amount == Decimal('40.00')
        assert result.currency == Currency.EUR

    def test_rejects_division_by_zero(self):
        money = Money.from_value('100',Currency.EUR)

        with pytest.raises(InvalidMoneyAmountError):
            money.divide(0)

    @pytest.mark.parametrize(
            'factor',
            [
                'not-a-number',
                'NaN',
                'Infinity',
                '-Infinity',
            ]
    )
    def test_rejects_invalid_multiplication_factor(self, factor):
        money = Money.from_value('100', Currency.EUR)

        with pytest.raises(InvalidMoneyAmountError):
            money.multiply(factor)

    @pytest.mark.parametrize(
            'divisor',
            [
                'not-a-number',
                'NaN',
                'Infinity',
                '-Infinity',
            ]
    )
    def test_rejects_invalid_divisor(self, divisor):
        money = Money.from_value('100', Currency.EUR)

        with pytest.raises(InvalidMoneyAmountError):
            money.divide(divisor)

class TestMoneyConversion:
    def test_converts_using_explicit_exchange_rate(self):
        money = Money.from_value('100', Currency.EUR)

        result = money.convert(Currency.USD,'1.10')

        assert isinstance(result, Money)
        assert result.amount == Decimal('110')
        assert result.currency == Currency.USD

    def test_conversion_does_not_mutate_original_money(self):
        money = Money.from_value('100', Currency.EUR)

        result = money.convert(Currency.USD,'1.10')

        assert money.amount == Decimal('100')
        assert money.currency == Currency.EUR
        
        assert result.amount == Decimal('110')
        assert result.currency == Currency.USD

    def test_same_currency_conversion_returns_same_value(self):
        money = Money.from_value('100', Currency.EUR)

        result = money.convert(Currency.EUR,'999.99')

        assert result == money

    @pytest.mark.parametrize(
        'rate',
        [
            'not-a-number',
            '0',
            '-1',
            'NaN',
            'Infinity',
            '-Infinity',
        ]
    )
    def test_rejects_invalid_exchange_rate(self,rate):
        money = Money.from_value('100', Currency.EUR)

        with pytest.raises(InvalidExchangeRateError):
            result = money.convert(Currency.USD, rate)

class TestMoneyState:
    def test_zero(self):
        money = Money.from_value('0',Currency.EUR)

        assert money.is_zero()
        assert not money.is_positive()
        assert not money.is_negative()

    def test_positive(self):
        money = Money.from_value('100',Currency.EUR)

        
        assert money.is_positive()
        assert not money.is_negative()
        assert not money.is_zero()

    def test_negative(self):
        money = Money.from_value('-100',Currency.EUR)

        
        assert money.is_negative()
        assert not money.is_positive()
        assert not money.is_zero()

    def test_money_is_not_mutable(self):

            money = Money.from_value('100',Currency.EUR)
    
            with pytest.raises(FrozenInstanceError):
                money.amount = Decimal('200')
            
