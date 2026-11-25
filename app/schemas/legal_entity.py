from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedModel


class LegalEntityCreateRequest(BaseModel):
    company_id: UUID
    name: str = Field(min_length=1, max_length=100)


class LegalEntityUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class LegalEntityResponse(TimestampedModel):
    company_id: UUID
    name: str
