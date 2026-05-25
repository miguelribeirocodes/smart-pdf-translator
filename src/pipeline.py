"""
Pipeline: orquestrador principal.

Une extractor -> grouper -> translator -> writer com callback de progresso.
Usado pelo backend FastAPI e pela CLI.

Problema 3:
- Spans agrupados em TextBlocks antes de traduzir.
- Cada bloco (paragrafo) e traduzido como uma unica string coerente.
- Escrita feita via write_translated_pdf_blocks() (novo writer).
- Reducao de chamadas ao tradutor: de N spans para M blocos (M << N tipicamente).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from .extractor import extract_spans, page_count
from .glossary import Glossary
from .grouper import group_into_blocks
from .translator import TranslationService
from .writer import write_translated_pdf_blocks, _get_page_vertical_lines

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
    block_count: int
    cache_hits: int
    failed_blocks: int


def translate_pdf(
    input_pdf: str,
    output_pdf: str,
    source_lang: str = "en",
    target_lang: str = "pt",
    provider: str = "google",
    fallbacks: Optional[list[str]] = None,
    on_progress: Optional[ProgressCallback] = None,
    request_delay: float = 0.05,
    glossary_path: Optional[str] = None,
) -> TranslationResult:
    """
    Traduz um PDF in-place preservando layout.

    Fluxo:
        extract_spans -> group_into_blocks -> translate (por bloco)
        -> write_translated_pdf_blocks

    Args:
        input_pdf:      caminho do PDF original.
        output_pdf:     caminho onde salvar o PDF traduzido.
        source_lang:    codigo do idioma de origem ('en', 'pt', 'es', ...).
        target_lang:    codigo do idioma de destino.
        provider:       provedor principal de traducao ('google', 'mymemory').
        fallbacks:      lista de provedores de fallback.
        on_progress:    callback opcional para reportar progresso.
        request_delay:  delay entre chamadas ao tradutor (segundos).
        glossary_path:  caminho para JSON de glossario (opcional).

    Returns:
        TranslationResult com estatisticas do processo.
    """
    if fallbacks is None:
        fallbacks = ["mymemory"] if provider != "mymemory" else []

    def _report(stage: str, pct: float) -> None:
        if on_progress:
            on_progress(stage, pct)
        log.info("[%5.1f%%] %s", pct, stage)

    # --- Extracao ---
    _report("Extraindo texto do PDF", 5.0)
    spans = extract_spans(input_pdf)
    pages = page_count(input_pdf)
    _report(f"Texto extraido: {len(spans)} spans em {pages} paginas", 10.0)

    if not spans:
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
            block_count=0,
            cache_hits=0,
            failed_blocks=0,
        )

    # --- Deteccao de bordas verticais (Sessao #10) ---
    # Pre-calcular bordas verticais por pagina para o grouper usar como sinal
    # adicional de separacao de celulas adjacentes coladas. O writer tambem
    # recalcula essas bordas na fase de escrita; o custo e baixo (O(drawings)).
    _report("Detectando bordas verticais (tabelas)", 12.0)
    import pymupdf
    v_lines_by_page: dict[int, list[float]] = {}
    _doc = pymupdf.open(input_pdf)
    try:
        for _p_idx in range(len(_doc)):
            v_lines_by_page[_p_idx] = _get_page_vertical_lines(_doc[_p_idx])
    finally:
        _doc.close()
    _report(
        f"Bordas verticais detectadas em {sum(1 for v in v_lines_by_page.values() if v)} paginas",
        13.0,
    )

    # --- Agrupamento em blocos (Problema 3 + Sessao #10 refinamento) ---
    blocks = group_into_blocks(spans, v_lines_by_page=v_lines_by_page)
    _report(
        f"Agrupados em {len(blocks)} blocos (era {len(spans)} spans individuais)",
        15.0,
    )

    # --- Traducao por bloco ---
    # --- Glossario ---
    glossary: Optional[Glossary] = None
    if glossary_path:
        try:
            glossary = Glossary.load(glossary_path)
            _report(f"Glossario carregado: {len(glossary)} termos protegidos", 15.0)
        except Exception as e:  # noqa: BLE001
            log.warning("Nao foi possivel carregar glossario %r: %s", glossary_path, e)

    # --- Traducao por bloco ---
    svc = TranslationService(primary=provider, fallbacks=fallbacks, request_delay=request_delay, glossary=glossary)
    translations: list[str] = []
    failed = 0
    total = len(blocks)

    for i, block in enumerate(blocks):
        try:
            translated = svc.translate(block.text, source=source_lang, target=target_lang)
            translations.append(translated)
        except Exception as e:  # noqa: BLE001
            log.warning("Falha traduzindo bloco %d (pag %d): %s", i, block.page, e)
            translations.append(block.text)
            failed += 1

        # Progresso de 15% a 90% ao longo dos blocos
        pct = 15.0 + (i + 1) / total * 75.0
        if i % max(1, total // 20) == 0 or i == total - 1:
            _report(f"Traduzindo bloco {i + 1}/{total}", pct)

    cache_hits = len(svc._cache)

    # --- Escrita ---
    _report("Reescrevendo PDF com texto traduzido", 92.0)
    write_translated_pdf_blocks(input_pdf, output_pdf, blocks, translations)
    _report("Concluido", 100.0)

    return TranslationResult(
        input_pdf=input_pdf,
        output_pdf=output_pdf,
        source_lang=source_lang,
        target_lang=target_lang,
        page_count=pages,
        span_count=len(spans),
        block_count=len(blocks),
        cache_hits=cache_hits,
        failed_blocks=failed,
    )
