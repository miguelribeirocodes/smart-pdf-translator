"""
Translator: wrapper sobre provedores de traducao.

Fase 0:
- Provider padrao: Google via deep-translator (gratuito, sem API key).
- Fallback automatico para MyMemory se Google falhar.
- Cache em memoria por (source, target, texto) para evitar traduzir o mesmo
  termo varias vezes (cabecalhos, rodapes, "Page X of Y", etc.).

Arquitetura:
- Interface Translator e implementacoes concretas.
- get_translator(provider) facilita trocar para Claude/DeepL/OpenAI no futuro
  apenas adicionando uma nova classe.
"""
from __future__ import annotations

import logging
import time
from typing import List, Protocol

from deep_translator import GoogleTranslator, MyMemoryTranslator
from deep_translator.exceptions import (
    RequestError,
    TooManyRequests,
    TranslationNotFound,
)

log = logging.getLogger(__name__)


class TranslatorProvider(Protocol):
    """Interface comum para provedores de traducao."""

    name: str

    def translate(self, text: str, source: str, target: str) -> str: ...


class GoogleProvider:
    name = "google"

    def translate(self, text: str, source: str, target: str) -> str:
        # deep-translator usa codigos de idioma curtos: 'en', 'pt', 'es', ...
        # Para portugues do Brasil, 'pt' funciona; para PT-PT use 'pt-PT'
        return GoogleTranslator(source=source, target=target).translate(text)


class MyMemoryProvider:
    name = "mymemory"

    @staticmethod
    def _expand(code: str) -> str:
        # MyMemory exige codigos longos (en-US, pt-BR)
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
    ):
        self.primary = get_translator(primary)
        self.fallbacks = [get_translator(n) for n in (fallbacks or [])]
        self.request_delay = request_delay
        self._cache: dict[tuple[str, str, str], str] = {}

    def translate(self, text: str, source: str, target: str) -> str:
        # Strings triviais nao precisam de API
        stripped = text.strip()
        if not stripped:
            return text
        if len(stripped) < 2 and not stripped.isalpha():
            return text  # numeros soltos, simbolos

        key = (source, target, text)
        if key in self._cache:
            return self._cache[key]

        last_err: Exception | None = None
        for provider in [self.primary, *self.fallbacks]:
            try:
                if self.request_delay:
                    time.sleep(self.request_delay)
                out = provider.translate(text, source, target)
                if out:
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

        # Todos falharam -> devolve original (mais seguro que travar pipeline)
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
