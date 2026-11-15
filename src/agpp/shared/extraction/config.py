"""Configuration of a delimited-file source, shared by every pipeline (ADR-0017)."""

from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator

from agpp.shared.models import AgppModel


class CsvSource(AgppModel):
    """A source file in CSV format."""

    type: Literal["csv"]
    path: str = Field(min_length=1)
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    encoding: str = "utf-8"


class ApiSource(AgppModel):
    """A paginated JSON-over-HTTP source (ADR-0018).

    The token is a secret: it is hidden in ``repr`` and meant to come from the
    environment through a placeholder. A blank token means no authentication.
    """

    type: Literal["api"]
    base_url: str = Field(pattern=r"^https?://\S+$")
    path: str = Field(default="/", pattern=r"^/\S*$")
    token: SecretStr | None = None
    timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    page_size: int = Field(default=500, ge=1, le=10_000)

    @field_validator("token", mode="before")
    @classmethod
    def _blank_token_means_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value
