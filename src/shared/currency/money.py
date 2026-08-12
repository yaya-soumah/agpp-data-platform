from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .currency import Currency

class MoneyError(ValueError):
    """Base exception for monetary value errors."""
    pass

class CurrencyMismatchError(MoneyError):
    """Raised when arithemetic is attempted between different currencies."""
    pass

class InvalidMoneyAmountError(MoneyError):
    """"Raised when a monetary cannot be represented as Decimal. """
    pass

class InvalidExchangeRateError(MoneyError):
    """Raised when an exchange rate is invalid."""
    pass

@dataclass(frozen=True, slots=True)
class Money:
    """Immutable monetary value consisting of an amount and currency."""

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidMoneyAmountError(
                "Money amount must be a Decimal."
            )

        if not isinstance(self.currency, Currency):
            raise TypeError(
                "Money currency must be an instance of Currency."
            )

    @classmethod
    def from_value(
        cls,
        amount: Decimal | int |str,
        currency: Currency,
    ) -> Money:
        """Create a Money value from a supported numeric representation."""
        try:
            decimal_amount = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise InvalidMoneyAmountError(
                f"Invalid monetary amount: {amount!r}"
            ) from e

        if not decimal_amount.is_finite():
            raise InvalidMoneyAmountError(
                "Monetary amount must be finite"
            )

        return cls(amount=decimal_amount, currency=currency)

    def _ensure_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot operate on {self.currency} and {other.currency}"
            )

    def add(self, other: Money) -> Money:
        """Add two monetary values of the same currency."""
        self._ensure_same_currency(other)
        return Money(
            amount=self.amount + other.amount,
            currency=self.currency
        )

    def subtract(self, other: Money) -> Money:
        """Subtract two monetary values of the same currency."""
        self._ensure_same_currency(other)
        return Money(
            amount=self.amount - other.amount,
            currency=self.currency
        )

    def multiply(self, factor: Decimal | int | str) -> Money:
        """Multiply a monetary value by a numeric factor."""
        try:
            decimal_factor = Decimal(str(factor))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise InvalidMoneyAmountError(
                f"Invalid multiplication factor: {factor!r}"
            ) from e

        if not decimal_factor.is_finite():
            raise InvalidMoneyAmountError(
                "Multiplication factor must be finite"
            )

        return Money(
            amount=self.amount * decimal_factor,
            currency=self.currency
        )

    def divide(self, divisor: Decimal | int | str) -> Money:
        """Divide a monetary value by a non-zero scalar."""
        try:
            decimal_divisor = Decimal(str(divisor))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise InvalidMoneyAmountError(
                f"Invalid division divisor: {divisor!r}"
            ) from e

        if not decimal_divisor.is_finite():
            raise InvalidMoneyAmountError(
                "Division divisor must be finite"
            )

        if decimal_divisor == 0:
            raise InvalidMoneyAmountError(
                "Division by zero is not allowed"
            )

        return Money(
            amount=self.amount / decimal_divisor,
            currency=self.currency
        )

    def convert(
            self, 
            target_currency: Currency,
            exchange_rate: Decimal | int | str, 
            ) -> Money:
        """Convert this monetary value using an explicitly supplied exchange rate.
        The exchange rate represents:
        1 source_currency = exchange_rate target_currency
        """

        if self.currency == target_currency:
            return self
        try:
            rate = Decimal(str(exchange_rate))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise InvalidExchangeRateError(
                f"Invalid exchange rate: {exchange_rate!r}"
            ) from exc

        if not rate.is_finite() or rate <= 0:
            raise InvalidExchangeRateError(
                "Exchange rate must be a positive finite Decimal."
            )

        return Money(
            amount=self.amount * rate,
            currency=target_currency
        )

    def is_zero(self) -> bool:
        """Check if the monetary value is zero."""
        return self.amount == Decimal("0")

    def is_positive(self) -> bool:
        """Check if the monetary value is positive."""
        return self.amount > Decimal("0")

    def is_negative(self) -> bool:
        """Check if the monetary value is negative."""
        return self.amount < Decimal("0")