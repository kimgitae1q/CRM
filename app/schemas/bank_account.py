from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedModel


class BankAccountCreateRequest(BaseModel):
    legal_entity_id: UUID
    name: str = Field(min_length=1, max_length=100)
    bik: str = Field(pattern=r"^\d{9}$")
    bank_name: str
    bank_address: str
    correspondent_account: str = Field(pattern=r"^\d{20}$")
    settlement_account: str = Field(pattern=r"^\d{20}$")
    currency: str
    comment: str | None = None


class BankAccountUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    bik: str = Field(pattern=r"^\d{9}$")
    bank_name: str
    bank_address: str
    correspondent_account: str = Field(pattern=r"^\d{20}$")
    settlement_account: str = Field(pattern=r"^\d{20}$")
    currency: str
    comment: str | None = None


class BankAccountResponse(TimestampedModel):
    legal_entity_id: UUID
    name: str
    bik: str
    bank_name: str
    bank_address: str
    correspondent_account: str
    settlement_account: str
    currency: str
    comment: str | None
    is_primary: bool
