from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from obliq_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organisation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organisations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    credit_balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    starting_grant: Mapped[int] = mapped_column(BigInteger, nullable=False, default=10_000)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    users: Mapped[list["User"]] = relationship(back_populates="organisation", lazy="selectin")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="organisation", lazy="selectin")
    ledger_entries: Mapped[list["CreditLedger"]] = relationship(
        back_populates="organisation", lazy="noload"
    )


# Avoid circular import issues at runtime
from obliq_api.models.api_key import ApiKey  # noqa: E402
from obliq_api.models.credit_ledger import CreditLedger  # noqa: E402
from obliq_api.models.user import User  # noqa: E402
