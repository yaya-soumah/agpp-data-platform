from dataclasses import dataclass
from typing import Protocol

import polars as pl


@dataclass(frozen=True)
class CustomerOrdersBatch:
    customers: pl.DataFrame
    orders: pl.DataFrame
    order_lines: pl.DataFrame


class CustomerOrdersExtractor(Protocol):
    def extract(self) -> CustomerOrdersBatch:
        """Extract one complete customer-orders batch."""
        ...
