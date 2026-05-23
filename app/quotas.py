"""
Cotas e rate-limit placeholder.

Na Fase 0, nenhuma cota e aplicada.
Estrutura prevista:
- por usuario: paginas/mes, paginas/dia
- por IP (anonimo): 5 PDFs/dia, max 50 paginas/PDF
- integracao com billing.py para liberar cota apos pagamento
"""
from __future__ import annotations

from .auth import User


class QuotaExceeded(Exception):
    pass


def check_quota(user: User, pages_estimate: int) -> None:
    """
    Levanta QuotaExceeded se o usuario passou da cota.
    Fase 0: noop.
    """
    # TODO: consultar contador no Redis/DB e comparar com user.plan
    return None
