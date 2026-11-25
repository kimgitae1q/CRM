from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.legal_entity import LegalEntity
from app.repositories.common import active


class LegalEntityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, legal_entity: LegalEntity) -> LegalEntity:
        self.session.add(legal_entity)
        await self.session.flush()
        await self.session.refresh(legal_entity)
        return legal_entity

    async def get(self, legal_entity_id: UUID) -> LegalEntity | None:
        query = (
            active(select(LegalEntity), LegalEntity)
            .where(LegalEntity.id == legal_entity_id)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(query)

    async def find_by_name(self, name: str, company_id: UUID) -> LegalEntity | None:
        query = active(select(LegalEntity), LegalEntity).where(
            LegalEntity.company_id == company_id, LegalEntity.name == name
        )
        return await self.session.scalar(query)

    async def list_by_company(self, company_id: UUID) -> list[LegalEntity]:
        query = active(select(LegalEntity), LegalEntity).where(
            LegalEntity.company_id == company_id
        )
        result = await self.session.scalars(query)
        return list(result.unique())
