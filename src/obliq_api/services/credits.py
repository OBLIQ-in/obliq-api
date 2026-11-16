from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.config import get_settings
from obliq_api.exceptions import InsufficientCreditsError
from obliq_api.models.credit_ledger import CreditLedger
from obliq_api.models.organisation import Organisation

settings = get_settings()


class CreditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_balance(self, organisation_id: UUID) -> int:
        result = await self.session.execute(
            select(Organisation.credit_balance).where(Organisation.id == organisation_id)
        )
        balance = result.scalar_one_or_none()
        if balance is None:
            raise ValueError("Organisation not found")
        return int(balance)

    async def reserve(
        self,
        organisation_id: UUID,
        pages: int,
        *,
        reference_id: str,
        idempotency_key: str | None = None,
        is_internal: bool = False,
    ) -> int:
        """Reserve credits. Returns amount reserved (0 for internal)."""
        if is_internal or pages <= 0:
            return 0

        amount = pages * settings.credits_per_page

        # Idempotency check
        if idempotency_key:
            existing = await self.session.execute(
                select(CreditLedger).where(
                    CreditLedger.organisation_id == organisation_id,
                    CreditLedger.idempotency_key == idempotency_key,
                    CreditLedger.entry_type == "reserve",
                )
            )
            if existing.scalar_one_or_none():
                return amount

        # Atomic conditional update
        stmt = (
            update(Organisation)
            .where(
                Organisation.id == organisation_id,
                Organisation.credit_balance >= amount,
            )
            .values(credit_balance=Organisation.credit_balance - amount)
            .returning(Organisation.credit_balance)
        )
        result = await self.session.execute(stmt)
        new_balance = result.scalar_one_or_none()
        if new_balance is None:
            current = await self.get_balance(organisation_id)
            raise InsufficientCreditsError(remaining=current)

        entry = CreditLedger(
            organisation_id=organisation_id,
            entry_type="reserve",
            amount=-amount,
            balance_after=new_balance,
            reference_type="job",
            reference_id=reference_id,
            idempotency_key=idempotency_key,
        )
        self.session.add(entry)
        await self.session.flush()
        return amount

    async def settle(
        self,
        organisation_id: UUID,
        reserved: int,
        actual_pages: int,
        *,
        reference_id: str,
        is_internal: bool = False,
    ) -> int:
        """Settle: charge actual pages, refund difference if over-reserved."""
        if is_internal:
            return 0

        actual = actual_pages * settings.credits_per_page
        if actual == reserved:
            # Convert reserve into settle (ledger only)
            entry = CreditLedger(
                organisation_id=organisation_id,
                entry_type="settle",
                amount=0,
                balance_after=await self.get_balance(organisation_id),
                reference_type="job",
                reference_id=reference_id,
                metadata_={"reserved": reserved, "actual": actual},
            )
            self.session.add(entry)
            await self.session.flush()
            return actual

        if actual < reserved:
            refund = reserved - actual
            stmt = (
                update(Organisation)
                .where(Organisation.id == organisation_id)
                .values(credit_balance=Organisation.credit_balance + refund)
                .returning(Organisation.credit_balance)
            )
            result = await self.session.execute(stmt)
            new_balance = result.scalar_one()
            self.session.add(
                CreditLedger(
                    organisation_id=organisation_id,
                    entry_type="refund",
                    amount=refund,
                    balance_after=new_balance,
                    reference_type="job",
                    reference_id=reference_id,
                )
            )
            await self.session.flush()
            return actual

        # actual > reserved (should be rare) – charge the difference
        extra = actual - reserved
        stmt = (
            update(Organisation)
            .where(
                Organisation.id == organisation_id,
                Organisation.credit_balance >= extra,
            )
            .values(credit_balance=Organisation.credit_balance - extra)
            .returning(Organisation.credit_balance)
        )
        result = await self.session.execute(stmt)
        extra_balance = result.scalar_one_or_none()
        if extra_balance is None:
            # Not enough for the extra; leave as reserved amount
            return reserved

        self.session.add(
            CreditLedger(
                organisation_id=organisation_id,
                entry_type="settle",
                amount=-extra,
                balance_after=extra_balance,
                reference_type="job",
                reference_id=reference_id,
            )
        )
        await self.session.flush()
        return actual

    async def refund(
        self,
        organisation_id: UUID,
        amount: int,
        *,
        reference_id: str,
        is_internal: bool = False,
    ) -> None:
        if is_internal or amount <= 0:
            return
        stmt = (
            update(Organisation)
            .where(Organisation.id == organisation_id)
            .values(credit_balance=Organisation.credit_balance + amount)
            .returning(Organisation.credit_balance)
        )
        result = await self.session.execute(stmt)
        new_balance = result.scalar_one()
        self.session.add(
            CreditLedger(
                organisation_id=organisation_id,
                entry_type="refund",
                amount=amount,
                balance_after=new_balance,
                reference_type="job",
                reference_id=reference_id,
            )
        )
        await self.session.flush()

    async def grant_starting_credits(self, organisation_id: UUID) -> None:
        amount = settings.starting_credits
        stmt = (
            update(Organisation)
            .where(Organisation.id == organisation_id)
            .values(credit_balance=Organisation.credit_balance + amount)
            .returning(Organisation.credit_balance)
        )
        result = await self.session.execute(stmt)
        new_balance = result.scalar_one()
        self.session.add(
            CreditLedger(
                organisation_id=organisation_id,
                entry_type="grant",
                amount=amount,
                balance_after=new_balance,
                reference_type="signup",
                reference_id=str(organisation_id),
            )
        )
        await self.session.flush()
