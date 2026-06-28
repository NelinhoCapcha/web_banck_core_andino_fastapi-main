from __future__ import annotations

from decimal import Decimal

from .engines import ITFEngine, InterestEngine, PenaltyEngine, money


class InstallmentService:
    INSURANCE_MONTHLY_RATE = Decimal("0.0008")

    @classmethod
    def insurance(cls, original_principal: Decimal) -> Decimal:
        return money(Decimal(str(original_principal or 0)) * cls.INSURANCE_MONTHLY_RATE)

    @classmethod
    def breakdown(
        cls,
        *,
        balance: Decimal,
        tea: Decimal,
        capital: Decimal,
        days: int = 30,
        original_principal: Decimal | None = None,
        overdue_days: int = 0,
    ) -> dict:
        interest = InterestEngine.effective_interest(balance, tea, days)
        insurance = cls.insurance(original_principal if original_principal is not None else balance)
        compensatory_late_interest = InterestEngine.effective_interest(balance, tea, overdue_days)
        penalty = PenaltyEngine.lookup_penalty(Decimal(str(capital or 0)) + interest + insurance, overdue_days)
        subtotal = money(Decimal(str(capital or 0)) + interest + insurance + compensatory_late_interest + penalty)
        itf = ITFEngine.calculate(subtotal)
        return {
            "capital": money(capital),
            "interest": interest,
            "insurance": insurance,
            "late_compensatory_interest": compensatory_late_interest,
            "penalty": penalty,
            "itf": itf,
            "installment": money(subtotal + itf),
        }
