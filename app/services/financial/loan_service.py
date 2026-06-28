from __future__ import annotations

from decimal import Decimal

from .engines import AmortizationEngine, ITFEngine, InterestEngine, TCEAEngine, money
from .installment_service import InstallmentService


class LoanService:
    @staticmethod
    def classify(codtipocredito: str | None) -> dict:
        code = (codtipocredito or "").strip().upper()
        mapping = {
            "01": ("ME", "Microempresa", "Microfinanzas: tasa segun riesgo y garantia del negocio."),
            "ME": ("ME", "Microempresa", "Microfinanzas: tasa segun riesgo y garantia del negocio."),
            "02": ("PE", "Pequena Empresa", "PYME: tasa segun perfil, antiguedad y garantia."),
            "PE": ("PE", "Pequena Empresa", "PYME: tasa segun perfil, antiguedad y garantia."),
            "03": ("CO", "Consumo", "TEA referencial 50.00% a 259.40% segun evaluacion."),
            "CO": ("CO", "Consumo", "TEA referencial 50.00% a 259.40% segun evaluacion."),
            "BTB": ("BTB", "Credito con garantia", "Back to Back: TEA referencial 19.00%."),
            "GNV": ("GNV", "Vehicular/GNV", "Vehicular o GNV: TEA referencial 30.00% a 50.00%."),
        }
        cod, name, note = mapping.get(code, (code or "OTRO", "Credito", "Tasa segun evaluacion crediticia."))
        return {"codigo": cod, "nombre": name, "nota": note}

    @staticmethod
    def fixed_schedule(principal: Decimal, tea: Decimal, months: int) -> dict:
        quota_without_insurance = AmortizationEngine.fixed_installment(principal, tea, months)
        balance = Decimal(str(principal or 0))
        rows = []
        cash_flows = [money(balance - ITFEngine.calculate(balance))]
        for nro in range(1, months + 1):
            interest = InterestEngine.effective_interest(balance, tea, 30)
            capital = money(quota_without_insurance - interest)
            if nro == months:
                capital = money(balance)
            insurance = InstallmentService.insurance(principal)
            subtotal = money(capital + interest + insurance)
            itf = ITFEngine.calculate(subtotal)
            installment = money(subtotal + itf)
            balance = AmortizationEngine.apply_capital_payment(balance, capital)
            cash_flows.append(-installment)
            rows.append(
                {
                    "nrocuota": nro,
                    "cuota": installment,
                    "capital": capital,
                    "interes": interest,
                    "seguro": insurance,
                    "itf": itf,
                    "saldo": balance,
                }
            )
        return {
            "cuota_referencial": rows[0]["cuota"] if rows else money(0),
            "tcea": TCEAEngine.annual_effective_cost(cash_flows),
            "cronograma": rows,
        }
