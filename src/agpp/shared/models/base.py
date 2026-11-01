"""Base class for business models."""

from pydantic import BaseModel, ConfigDict


class AgppModel(BaseModel):
    """Immutable model that rejects unknown fields and trims surrounding whitespace."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)
