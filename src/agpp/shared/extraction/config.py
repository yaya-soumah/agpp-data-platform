"""Configuration of a delimited-file source, shared by every pipeline (ADR-0017)."""

from typing import Literal

from pydantic import Field

from agpp.shared.models import AgppModel


class CsvSource(AgppModel):
    """A source file in CSV format."""

    type: Literal["csv"]
    path: str = Field(min_length=1)
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    encoding: str = "utf-8"
