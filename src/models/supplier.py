from pydantic import AnyUrl, BaseModel, ConfigDict, EmailStr, Field


class Supplier(BaseModel):
    """Business entity representing a supplier."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    supplier_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    country: str = Field(min_length=1)
    address: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    website: AnyUrl | None = None
