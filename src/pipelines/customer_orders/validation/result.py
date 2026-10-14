from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class ValidationResult:
    valid: pl.DataFrame
    rejected: pl.DataFrame
