from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.legal_entity import LegalEntity


class BankAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bank_accounts"

    name: Mapped[str] = mapped_column(String(100))
    bik: Mapped[str] = mapped_column(String)
    bank_name: Mapped[str] = mapped_column(String)
    bank_address: Mapped[str] = mapped_column(String)
    correspondent_account: Mapped[str] = mapped_column(String)
    settlement_account: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String)
    comment: Mapped[str | None] = mapped_column(String)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    legal_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="CASCADE")
    )

    legal_entity: Mapped["LegalEntity"] = relationship(back_populates="bank_accounts")

    def __str__(self) -> str:
        return self.name
