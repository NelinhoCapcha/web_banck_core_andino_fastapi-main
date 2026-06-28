from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28

MONEY = Decimal("0.01")
PERCENT_BASE = Decimal("100")
YEAR_DAYS = Decimal("360")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def rate(value: Decimal | int | float | str) -> Decimal:
    raw = Decimal(str(value or 0))
    return raw / PERCENT_BASE if raw > 1 else raw


class InterestEngine:
    @staticmethod
    def effective_interest(balance: Decimal, tea: Decimal, days: int) -> Decimal:
        principal = Decimal(str(balance or 0))
        if principal <= 0 or days <= 0:
            return money(0)
        annual_rate = rate(tea)
        factor = (Decimal(1) + annual_rate) ** (Decimal(days) / YEAR_DAYS)
        return money(principal * (factor - Decimal(1)))

    @staticmethod
    def monthly_effective_rate(tea: Decimal) -> Decimal:
        annual_rate = rate(tea)
        return (Decimal(1) + annual_rate) ** (Decimal(1) / Decimal(12)) - Decimal(1)


class AmortizationEngine:
    @staticmethod
    def fixed_installment(balance: Decimal, tea: Decimal, months: int) -> Decimal:
        principal = Decimal(str(balance or 0))
        if principal <= 0 or months <= 0:
            return money(0)
        tem = InterestEngine.monthly_effective_rate(tea)
        if tem == 0:
            return money(principal / Decimal(months))
        factor = (Decimal(1) + tem) ** Decimal(months)
        return money(principal * tem * factor / (factor - Decimal(1)))

    @staticmethod
    def apply_capital_payment(balance: Decimal, capital: Decimal) -> Decimal:
        return money(max(Decimal(0), Decimal(str(balance or 0)) - Decimal(str(capital or 0))))


class PenaltyEngine:
    DEFAULT_BANDS = (
        (Decimal("0"), Decimal("250"), 1, 7, Decimal("5.00")),
        (Decimal("0"), Decimal("250"), 8, 30, Decimal("10.00")),
        (Decimal("250.01"), Decimal("1000"), 1, 7, Decimal("10.00")),
        (Decimal("250.01"), Decimal("1000"), 8, 30, Decimal("25.00")),
        (Decimal("1000.01"), Decimal("999999999"), 1, 7, Decimal("25.00")),
        (Decimal("1000.01"), Decimal("999999999"), 8, 30, Decimal("50.00")),
        (Decimal("0"), Decimal("999999999"), 31, 99999, Decimal("75.00")),
    )

    @classmethod
    def lookup_penalty(cls, installment_amount: Decimal, overdue_days: int) -> Decimal:
        amount = Decimal(str(installment_amount or 0))
        if overdue_days <= 0:
            return money(0)
        for min_amount, max_amount, min_days, max_days, penalty in cls.DEFAULT_BANDS:
            if min_amount <= amount <= max_amount and min_days <= overdue_days <= max_days:
                return money(penalty)
        return money(0)


class ITFEngine:
    RATE = Decimal("0.00005")  # 0.005%

    @classmethod
    def calculate(cls, transaction_amount: Decimal) -> Decimal:
        return money(Decimal(str(transaction_amount or 0)) * cls.RATE)


class TCEAEngine:
    @staticmethod
    def irr(cash_flows: list[Decimal], guess: Decimal = Decimal("0.03")) -> Decimal | None:
        if not cash_flows or not any(c > 0 for c in cash_flows) or not any(c < 0 for c in cash_flows):
            return None
        r = guess
        for _ in range(80):
            npv = Decimal(0)
            deriv = Decimal(0)
            for idx, flow in enumerate(cash_flows):
                denom = (Decimal(1) + r) ** Decimal(idx)
                npv += flow / denom
                if idx:
                    deriv -= Decimal(idx) * flow / ((Decimal(1) + r) ** Decimal(idx + 1))
            if deriv == 0:
                return None
            new_r = r - (npv / deriv)
            if abs(new_r - r) < Decimal("0.0000001"):
                return new_r
            if new_r <= Decimal("-0.9999"):
                return None
            r = new_r
        return r

    @classmethod
    def annual_effective_cost(cls, cash_flows: list[Decimal]) -> Decimal | None:
        monthly_irr = cls.irr(cash_flows)
        if monthly_irr is None:
            return None
        tcea = ((Decimal(1) + monthly_irr) ** Decimal(12)) - Decimal(1)
        return (tcea * PERCENT_BASE).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
