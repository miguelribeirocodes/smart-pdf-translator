"""
Pipeline: orquestrador principal.

Une extractor -> translator -> writer com callback de progresso opcional.
Usado pelo backend FastAPI e pela CLI.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from .extractor import extract_spans, page_count
from .translator import TranslationService
from .writer import write_translated_pdf

log = logging.getLogger(__name__)


ProgressCallback = Callable[[str, float], None]
# (etapa, percentual 0-100) -> None


@dataclass
class TranslationResult:
    input_pdf: str
    output_pdf: str
    source_lang: str
    target_lang: str
    page_count: int
    span_count: int
    cache_hits: int
    failed_spans: int


def translate_pdf(
    input_pdf: str,
    output_pdf: str,
    source_lang: str = "en",
    target_lang: str = "pt",
    provider: str = "google",
    fallbacks: Optional[list[str]] = None,
    on_progress: Optional[ProgressCallback] = None,
    request_delay: float = 0.05,
) -> TranslationResult:
    """
    Traduz um PDF in-place preservando layout.

    Args:
        input_pdf: caminho do PDF original.
        output_pdf: caminho onde salvar o PDF traduzido.
        source_lang: codigo do idioma de origem ('en', 'pt', 'es', ...).
        target_lang: codigo do idioma de destino.
        provider: provedor principal de traducao ('google', 'mymemory').
        fallbacks: lista de provedores de fallback.
        on_progress: callback opcional para reportar progresso.

    Returns:
        TranslationResult com estatisticas do processo.
    """
    if fallbacks is None:
        fallbacks = ["mymemory"] if provider != "mymemory" else []

    def _report(stage: str, pct: float) -> None:
        if on_progress:
            on_progress(stage, pct)
        log.info("[%5.1f%%] %s", pct, stage)

    _report("Extraindo texto do PDF", 5.0)
    spans = extract_spans(input_pdf)
    pages = page_count(input_pdf)
    _report(f"Texto extraido: {len(spans)} blocos em {pages} paginas", 15.0)

    if not spans:
        # PDF escaneado ou vazio -> apenas copia
        log.warning("Nenhum span de texto encontrado. PDF pode ser escaneado.")
        _report("Nenhum texto encontrado (PDF escaneado?)", 100.0)
        import shutil
        shutil.copy(input_pdf, output_pdf)
        return TranslationResult(
            input_pdf=input_pdf,
            output_pdf=output_pdf,
            source_lang=source_lang,
            target_lang=target_lang,
            page_count=pages,
            span_count=0,
            cache_hits=0,
            failed_spans=0,
        )

    svc = TranslationService(primary=provider, fallbacks=fallbacks, request_delay=request_delay)

    translations: list[str] = []
    cache_before = 0
    failed = 0
    total = len(spans)
    for i, span in enumerate(spans):
        try:
            translated = svc.translate(
                span.text, source=source_lang, target=target_lang
            )
            if translated == span.text:
                # Pode ser cache hit em string trivial ou falha silenciosa
                pass
            translations.append(translated)
        except Exception as e:  # noqa: BLE001
            log.warning("Falha traduzindo span %d: %s", i, e)
            translations.append(span.text)
            failed += 1

        # Reporta progresso a cada 5% (intervalo 15-90%)
        pct = 15.0 + (i + 1) / total * 75.0
        if i % max(1, total // 20) == 0 or i == total - 1:
            _report(f"Traduzindo {i + 1}/{total}", pct)

    cache_hits = len(svc._cache)
    _report("Reescrevendo PDF com texto traduzido", 92.0)
    write_translated_pdf(input_pdf, output_pdf, spans, translations)
    _report("Concluido", 100.0)

    return TranslationResult(
        input_pdf=input_pdf,
        output_pdf=output_pdf,
        source_lang=source_lang,
        target_lang=target_lang,
        page_count=pages,
        span_count=len(spans),
        cache_hits=cache_hits,
        failed_spans=failed,
    )
