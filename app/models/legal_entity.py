from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.bank_account import BankAccount
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company


class LegalEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "legal_entities"

    name: Mapped[str] = mapped_column(String(100))

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )

    company: Mapped["Company"] = relationship(back_populates="legal_entities")
    bank_accounts: Mapped[list["BankAccount"]] = relationship(
        back_populates="legal_entity"
    )

    def __str__(self) -> str:
        return f"LegalEntity(name = {self.name}, company_id = {self.company_id})"
