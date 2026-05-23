"""
Auth placeholder.

Na Fase 0, todos os requests sao autenticados como 'anonymous'.
Quando for implementar de verdade:
- substituir `get_current_user` por um dependency que valida JWT/session;
- adicionar rotas /login, /signup, /logout em main.py;
- persistir usuarios em DB (substitui o dict abaixo).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    id: str
    email: str
    plan: str = "free"


ANONYMOUS = User(id="anonymous", email="anonymous@local", plan="free")


def get_current_user() -> User:
    """FastAPI dependency. Hoje sempre devolve usuario anonimo."""
    return ANONYMOUS
