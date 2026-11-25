from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import TimestampedModel


class LegalEntityCreateRequest(BaseModel):
    company_id: UUID
    name: str


class LegalEntityUpdateRequest(BaseModel):
    name: str


class LegalEntityResponse(TimestampedModel):
    company_id: UUID
    name: str
