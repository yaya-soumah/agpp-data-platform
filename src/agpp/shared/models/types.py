"""Reusable field types for business and configuration models (ADR-0017)."""

from typing import Annotated

from pydantic import StringConstraints

CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
