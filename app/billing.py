"""
Billing placeholder.

Interfaces previstas para futura integracao com Stripe e Mercado Pago.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Plan:
    code: str
    name: str
    price_brl: float
    pages_per_month: int
    description: str


# Catalogo provisorio de planos para o frontend "espiar" o futuro.
PLANS: list[Plan] = [
    Plan(
        code="free",
        name="Free",
        price_brl=0.0,
        pages_per_month=20,
        description="Para testar a ferramenta. 20 paginas/mes.",
    ),
    Plan(
        code="starter",
        name="Starter",
        price_brl=29.90,
        pages_per_month=500,
        description="Profissionais autonomos. 500 paginas/mes.",
    ),
    Plan(
        code="pro",
        name="Pro",
        price_brl=99.90,
        pages_per_month=3000,
        description="Pequenas empresas. 3.000 paginas/mes + glossario customizado.",
    ),
    Plan(
        code="business",
        name="Business",
        price_brl=299.90,
        pages_per_month=15000,
        description="Escritorios. 15.000 paginas/mes + suporte prioritario + multi-usuario.",
    ),
]


def create_checkout_session(plan_code: str, user_email: str) -> str:
    """
    Cria sessao de checkout no Stripe/Mercado Pago.
    Fase 0: noop.
    """
    raise NotImplementedError(
        "Billing nao implementado na Fase 0. "
        "Conecte Stripe ou Mercado Pago aqui."
    )
