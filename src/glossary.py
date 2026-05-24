"""
Glossario tecnico para termos protegidos.

Permite definir termos que NAO devem ser traduzidos (siglas, nomes proprios,
termos tecnicos especificos de projeto) ou que devem usar uma traducao forcada
independente do provedor externo.

Formato JSON em disco:
{
    "id":    "<uuid-hex>",
    "name":  "Nome do Glossario",
    "terms": {
        "CFTV":          "CFTV",
        "Novo Nordisk":  "Novo Nordisk",
        "scope of work": "escopo de trabalho"
    }
}

A chave e o termo de origem (source); o valor e o termo de destino (target).
Para termos protegidos (sem traducao), repita o mesmo texto em source e target.

Mecanismo:
    Antes de enviar ao provedor de traducao, `protect()` substitui cada
    termo de origem por um placeholder ASCII unico (__GLOSS0__, __GLOSS1__, ...).
    Apos receber o resultado traduzido, `restore()` troca os placeholders
    pelo termo de destino configurado no glossario.

    Termos mais longos sao substituidos primeiro para evitar matches parciais
    (ex.: "scope of work" antes de "scope").
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Prefixo dos placeholders de glossario -- diferente dos de caracteres especiais
_GLOSS_PREFIX = "__GLOSS"
_GLOSS_SUFFIX = "__"


class Glossary:
    """
    Glossario de termos com protect/restore para uso no TranslationService.

    Uso:
        g = Glossary(terms={"CFTV": "CFTV", "Novo Nordisk": "Novo Nordisk"})
        protected, mapping = g.protect("Install the CFTV system for Novo Nordisk.")
        translated = some_translator(protected)
        result = g.restore(translated, mapping)
    """

    def __init__(
        self,
        terms: dict[str, str],
        name: str = "",
        gid: str = "",
    ) -> None:
        self.id = gid or uuid.uuid4().hex
        self.name = name
        # Termos ordenados por comprimento decrescente: substituir "scope of work"
        # antes de "scope" evita matches parciais incorretos.
        self._terms_sorted: list[tuple[str, str]] = sorted(
            terms.items(), key=lambda x: len(x[0]), reverse=True
        )

    # ------------------------------------------------------------------
    # Protect / Restore
    # ------------------------------------------------------------------

    def protect(self, text: str) -> tuple[str, dict[str, str]]:
        """
        Substitui termos do glossario por placeholders unicos.

        Returns:
            (texto_com_placeholders, mapeamento {placeholder -> termo_destino})
            Se nenhum termo for encontrado, retorna (text, {}).
        """
        result = text
        mapping: dict[str, str] = {}
        slot = 0
        for src, tgt in self._terms_sorted:
            pattern = re.compile(re.escape(src), re.IGNORECASE)
            if pattern.search(result):
                placeholder = f"{_GLOSS_PREFIX}{slot}{_GLOSS_SUFFIX}"
                result = pattern.sub(placeholder, result)
                mapping[placeholder] = tgt
                slot += 1
        return result, mapping

    def restore(self, text: str, mapping: dict[str, str]) -> str:
        """Restaura placeholders com os termos de destino do glossario."""
        for placeholder, target in mapping.items():
            text = text.replace(placeholder, target)
        return text

    # ------------------------------------------------------------------
    # Serializacao
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "terms": {src: tgt for src, tgt in self._terms_sorted},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Glossary":
        return cls(
            terms=data.get("terms", {}),
            name=data.get("name", ""),
            gid=data.get("id", ""),
        )

    def save(self, path: str | Path) -> None:
        """Salva o glossario em um arquivo JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        log.debug("Glossario %r salvo em %s", self.name, p)

    @classmethod
    def load(cls, path: str | Path) -> "Glossary":
        """Carrega um glossario de um arquivo JSON."""
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def __len__(self) -> int:
        return len(self._terms_sorted)

    def __repr__(self) -> str:
        return f"Glossary(id={self.id!r}, name={self.name!r}, terms={len(self)})"
