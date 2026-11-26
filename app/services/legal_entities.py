from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.legal_entity import LegalEntity
from app.repositories.companies import CompanyRepository
from app.repositories.legal_entities import LegalEntityRepository


class LegalEntityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.legal_entity_repository = LegalEntityRepository(session)
        self.company_repository = CompanyRepository(session)

    async def get(self, legal_entity_id: UUID) -> LegalEntity:
        legal_entity = await self.legal_entity_repository.get(legal_entity_id)
        if not legal_entity:
            raise NotFoundError("Юр лицо не найдено")
        return legal_entity

    async def list_by_company(self, company_id: UUID) -> list[LegalEntity]:
        return await self.legal_entity_repository.list_by_company(company_id)

    async def create(self, name: str, company_id: UUID) -> LegalEntity:
        company = await self.company_repository.get_for_update(company_id)
        if company is None or company.deleted_at is not None:
            raise NotFoundError("Компания не найдена")

        await self._check_name_available(name, company_id)
        legal_entity = LegalEntity(name=name, company_id=company_id)
        await self.legal_entity_repository.create(legal_entity)
        await self.session.commit()
        await self.session.refresh(legal_entity)
        return legal_entity

    async def update(self, name: str, legal_entity_id: UUID) -> LegalEntity:
        legal_entity = await self.get(legal_entity_id)
        await self.company_repository.get_for_update(legal_entity.company_id)
        # Повторное чтение учитывает изменения, сделанные до получения блокировки.
        legal_entity = await self.get(legal_entity_id)
        if legal_entity.name != name:
            await self._check_name_available(name, legal_entity.company_id)
            legal_entity.name = name
        await self.session.commit()
        await self.session.refresh(legal_entity)
        return legal_entity

    async def _check_name_available(self, name: str, company_id: UUID) -> None:
        existing = await self.legal_entity_repository.find_by_name(
            name=name, company_id=company_id
        )
        if existing is not None:
            raise ConflictError("Юр лицо с таким именем уже найдено")
