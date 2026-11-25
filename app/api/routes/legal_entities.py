from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_legal_entity_service
from app.core.exceptions import ConflictError, NotFoundError
from app.models.user import User
from app.schemas.legal_entity import (
    LegalEntityCreateRequest,
    LegalEntityResponse,
    LegalEntityUpdateRequest,
)
from app.services.legal_entities import LegalEntityService

router = APIRouter(prefix="/legal_entities", tags=["legal_entities"])


@router.get("/{legal_entity_id}", response_model=LegalEntityResponse)
async def get_legal_entity(
    legal_entity_id: UUID,
    _: User = Depends(get_current_user),
    legal_entity_service: LegalEntityService = Depends(get_legal_entity_service),
) -> LegalEntityResponse:
    try:
        legal_entity = await legal_entity_service.get(legal_entity_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.detail)
    return LegalEntityResponse.model_validate(legal_entity)


@router.get("", response_model=list[LegalEntityResponse])
async def get_legal_entities_by_company(
    company_id: UUID,
    _: User = Depends(get_current_user),
    legal_entity_service: LegalEntityService = Depends(get_legal_entity_service),
) -> list[LegalEntityResponse]:
    try:
        legal_entities = await legal_entity_service.list_by_company(company_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.detail)
    return [
        LegalEntityResponse.model_validate(legal_entity)
        for legal_entity in legal_entities
    ]


@router.post("", response_model=LegalEntityResponse)
async def create_legal_entity(
    payload: LegalEntityCreateRequest,
    _: User = Depends(get_current_user),
    legal_entity_service: LegalEntityService = Depends(get_legal_entity_service),
) -> LegalEntityResponse:
    try:
        legal_entity = await legal_entity_service.create(
            name=payload.name, company_id=payload.company_id
        )
    except (NotFoundError, ConflictError) as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    return LegalEntityResponse.model_validate(legal_entity)


@router.patch("", response_model=LegalEntityResponse)
async def update_legal_entity(
    payload: LegalEntityUpdateRequest,
    legal_entity_id: UUID,
    _: User = Depends(get_current_user),
    legal_entity_service: LegalEntityService = Depends(get_legal_entity_service),
) -> LegalEntityResponse:
    try:
        legal_entity = await legal_entity_service.update(
            legal_entity_id=legal_entity_id, name=payload.name
        )
    except (NotFoundError, ConflictError) as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    return LegalEntityResponse.model_validate(legal_entity)
