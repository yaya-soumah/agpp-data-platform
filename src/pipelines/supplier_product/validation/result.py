from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class ValidationResult:
    """Represents the result of supplier=product validation."""

    valid: pl.DataFrame
    rejected: pl.DataFrame
