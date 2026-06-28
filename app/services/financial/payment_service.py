from __future__ import annotations

from decimal import Decimal

from .engines import ITFEngine, money


class PaymentService:
    @staticmethod
    def payment_summary(amount: Decimal) -> dict:
        base = money(amount)
        itf = ITFEngine.calculate(base)
        return {
            "amount": base,
            "itf": itf,
            "total_debited": money(base + itf),
        }
