"""
Translator: wrapper sobre provedores de traducao.

Fase 0:
- Provider padrao: Google via deep-translator (gratuito, sem API key).
- Fallback automatico para MyMemory se Google falhar.
- Cache em memoria por (source, target, texto) para evitar traduzir o mesmo
  termo varias vezes (cabecalhos, rodapes, "Page X of Y", etc.).

Protecao de caracteres especiais:
- Google Translate mangli caracteres Unicode fora do Latin-1 (en-dash, bullet,
  aspas tipograficas, etc.) devolvendo '?'.
- Antes de enviar, substituimos esses chars por placeholders ASCII unicos que
  o tradutor preserva; apos a traducao, restauramos os originais.
- Spans compostos APENAS de simbolos/numeros/espacos sao devolvidos sem traduzir.

Arquitetura:
- Interface Translator e implementacoes concretas.
- get_translator(provider) facilita trocar para Claude/DeepL/OpenAI no futuro
  apenas adicionando uma nova classe.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Protocol, Tuple

from deep_translator import GoogleTranslator, MyMemoryTranslator

# Import opcional para evitar circular; Glossary nao depende de translator
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .glossary import Glossary
from deep_translator.exceptions import (
    RequestError,
    TooManyRequests,
    TranslationNotFound,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protecao de caracteres especiais
# ---------------------------------------------------------------------------

# Caracteres que provedores gratuitos costumam mandar como '?'.
# Ordem importa: processar strings mais longas primeiro se houver ambiguidade.
_SPECIAL_CHARS: List[Tuple[str, str]] = [
    ("—", "__EMDASH__"),    # — em-dash
    ("–", "__ENDASH__"),    # – en-dash
    ("•", "__BULLET__"),    # • bullet
    ("‘", "__LSQUO__"),     # ' aspas esquerda simples
    ("’", "__RSQUO__"),     # ' aspas direita simples / apostrofe
    ("“", "__LDQUO__"),     # " aspas esquerda dupla
    ("”", "__RDQUO__"),     # " aspas direita dupla
    ("©", "__COPY__"),      # © copyright
    ("®", "__REG__"),       # ® registered
    ("™", "__TM__"),        # ™ trademark
    ("°", "__DEG__"),       # ° graus
    ("×", "__TIMES__"),     # × multiplicacao
    ("÷", "__DIV__"),       # ÷ divisao
    ("…", "__ELLIP__"),     # … reticencias
    # NBSP normalizado diretamente em _protect() sem placeholder
]

# Conjunto de chars especiais para deteccao rapida
_SPECIAL_SET = {ch for ch, _ in _SPECIAL_CHARS}

# Regex para detectar se um texto tem conteudo alfabetico traduzivel
_HAS_ALPHA = re.compile(r"[a-zA-ZÀ-ɏЀ-ӿ]")


def _protect(text: str) -> Tuple[str, bool]:
    """
    Substitui caracteres especiais por placeholders ASCII.

    Tambem normaliza NBSP para espaco normal (nao precisa restaurar).
    Retorna (texto_protegido, houve_substituicao).
    """
    # Normalizar NBSP antes de qualquer outra coisa
    text = text.replace("\u00a0", " ")
    modified = False
    for ch, placeholder in _SPECIAL_CHARS:
        if ch in text:
            text = text.replace(ch, placeholder)
            modified = True
    return text, modified


def _restore(text: str) -> str:
    """Restaura placeholders de volta aos caracteres originais."""
    for ch, placeholder in _SPECIAL_CHARS:
        if placeholder in text:
            text = text.replace(placeholder, ch)
    return text


def _is_untranslatable(text: str) -> bool:
    """
    Retorna True se o texto nao tem conteudo alfabetico e nao precisa de
    traducao (numeros, simbolos, bullets isolados, etc.).
    """
    stripped = text.strip()
    if not stripped:
        return True
    # So um caractere nao-alfabetico
    if len(stripped) == 1 and not stripped.isalpha():
        return True
    # Nenhuma letra (so numeros, pontuacao, espacos, simbolos especiais)
    if not _HAS_ALPHA.search(stripped):
        return True
    return False


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

class TranslatorProvider(Protocol):
    """Interface comum para provedores de traducao."""

    name: str

    def translate(self, text: str, source: str, target: str) -> str: ...


class GoogleProvider:
    name = "google"

    def translate(self, text: str, source: str, target: str) -> str:
        return GoogleTranslator(source=source, target=target).translate(text)


class MyMemoryProvider:
    name = "mymemory"

    @staticmethod
    def _expand(code: str) -> str:
        mapping = {
            "en": "en-US",
            "pt": "pt-BR",
            "es": "es-ES",
            "fr": "fr-FR",
            "de": "de-DE",
            "it": "it-IT",
        }
        return mapping.get(code, code)

    def translate(self, text: str, source: str, target: str) -> str:
        s = self._expand(source)
        t = self._expand(target)
        return MyMemoryTranslator(source=s, target=t).translate(text)


PROVIDERS = {
    "google": GoogleProvider(),
    "mymemory": MyMemoryProvider(),
}


def get_translator(name: str = "google") -> TranslatorProvider:
    if name not in PROVIDERS:
        raise ValueError(
            f"Provider desconhecido: {name!r}. Disponiveis: {list(PROVIDERS)}"
        )
    return PROVIDERS[name]


# ---------------------------------------------------------------------------
# Servico principal
# ---------------------------------------------------------------------------

class TranslationService:
    """
    Camada de servico que orquestra provedor + cache + fallback.

    Uso:
        svc = TranslationService(primary='google', fallbacks=['mymemory'])
        translated = svc.translate("Hello", source='en', target='pt')
    """

    def __init__(
        self,
        primary: str = "google",
        fallbacks: List[str] | None = None,
        request_delay: float = 0.0,
        glossary: "Glossary | None" = None,
    ):
        self.primary = get_translator(primary)
        self.fallbacks = [get_translator(n) for n in (fallbacks or [])]
        self.request_delay = request_delay
        self.glossary = glossary
        self._cache: dict[tuple[str, str, str], str] = {}

    def translate(self, text: str, source: str, target: str) -> str:
        # 1. Texto vazio ou so whitespace
        if not text or not text.strip():
            return text

        # 2. Sem conteudo traduzivel (so simbolos, numeros, bullets)
        if _is_untranslatable(text):
            return text

        # 3. Cache (chave = texto ORIGINAL para consistencia)
        key = (source, target, text)
        if key in self._cache:
            return self._cache[key]

        # 4a. Proteger termos do glossario (antes dos caracteres especiais)
        gmap: dict[str, str] = {}
        text_to_translate = text
        if self.glossary and len(self.glossary) > 0:
            text_to_translate, gmap = self.glossary.protect(text)

        # 4b. Proteger caracteres especiais antes de enviar ao provider
        protected, had_specials = _protect(text_to_translate)

        last_err: Exception | None = None
        for provider in [self.primary, *self.fallbacks]:
            try:
                if self.request_delay:
                    time.sleep(self.request_delay)
                raw_out = provider.translate(protected, source, target)
                if raw_out:
                    # 5a. Restaurar caracteres especiais no resultado
                    out = _restore(raw_out) if had_specials else raw_out
                    # 5b. Restaurar termos do glossario
                    if gmap:
                        out = self.glossary.restore(out, gmap)
                    self._cache[key] = out
                    return out
            except (RequestError, TooManyRequests, TranslationNotFound) as e:
                log.warning(
                    "Provider %s falhou em %r: %s", provider.name, text[:40], e
                )
                last_err = e
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "Provider %s erro inesperado em %r: %s",
                    provider.name,
                    text[:40],
                    e,
                )
                last_err = e

        log.error(
            "Todos os providers falharam para %r (ultimo erro: %s). "
            "Mantendo texto original.",
            text[:60],
            last_err,
        )
        return text

    def translate_batch(
        self, texts: List[str], source: str, target: str
    ) -> List[str]:
        return [self.translate(t, source, target) for t in texts]


# Idiomas suportados (codigo -> rotulo amigavel para a UI)
SUPPORTED_LANGUAGES = {
    "en": "Ingles",
    "pt": "Portugues",
    "es": "Espanhol",
    "fr": "Frances",
    "de": "Alemao",
    "it": "Italiano",
    "ja": "Japones",
    "zh-CN": "Chines (Simplificado)",
    "ru": "Russo",
    "nl": "Holandes",
}
