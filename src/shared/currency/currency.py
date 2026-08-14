from __future__ import annotations
from enum import StrEnum

class Currency(StrEnum):
    """ISO 4217 currency codes supported by AGPP"""

    EUR = "EUR"
    USD = "USD"
    CNY = "CNY"
    GBP = "GBP"