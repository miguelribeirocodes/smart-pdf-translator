"""
Writer: reescreve spans traduzidos in-place no PDF original.

Fase 0 (CRUA):
- Apaga o texto original cobrindo com retangulo branco e escreve o novo
  texto na mesma bbox usando insert_textbox.
- Usa NotoSans (via pymupdf-fonts) em vez das fontes base14 para garantir
  cobertura Unicode completa -- elimina os "?" que surgiam com helv/hebo.
- Se o texto traduzido nao couber na bbox original, reduz o tamanho da fonte
  progressivamente ate caber ou atingir 4pt (minimo).

Estrategia anti-quebra-de-layout:
- Pintamos um retangulo branco sobre o texto antigo (draw_rect).
- Inserimos o novo texto com insert_textbox, alinhamento esquerdo.
- A bbox de escrita e ligeiramente expandida horizontalmente para absorver
  a expansao tipica de texto traduzido (Problema 1 do briefing, tratamento
  minimo; solucao completa na Fase 1).

Sobre as fontes:
- pymupdf-fonts (pip install pymupdf-fonts) fornece NotoSans com ~3246
  glifos cobrindo Latin, Cirilico, Grego, Hebraico, Arabico, CJK basico, etc.
- Registramos as 4 variantes (regular, bold, italic, bold-italic) uma vez
  por documento para evitar registros duplicados por pagina.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import pymupdf

try:
    import pymupdf_fonts as _mf
    _FONT_BUFFERS: Dict[str, bytes] = {
        "notos":   _mf.fontbuffers["notos"],    # NotoSans Regular
        "notosbo": _mf.fontbuffers["notosbo"],  # NotoSans Bold
        "notosit": _mf.fontbuffers["notosit"],  # NotoSans Italic
        "notosbi": _mf.fontbuffers["notosbi"],  # NotoSans Bold Italic
    }
    _HAS_NOTO = True
except Exception:  # noqa: BLE001
    _FONT_BUFFERS = {}
    _HAS_NOTO = False

from .extractor import TextSpan

log = logging.getLogger(__name__)

if not _HAS_NOTO:
    log.warning(
        "pymupdf-fonts nao encontrado. Usando fontes base14 (Latin-1 apenas). "
        "Instale com: pip install pymupdf-fonts"
    )

# Nomes internos das fontes Noto registradas no documento
_NOTO_REGULAR     = "notos"
_NOTO_BOLD        = "notosbo"
_NOTO_ITALIC      = "notosit"
_NOTO_BOLD_ITALIC = "notosbi"

# Fallback base14 se pymupdf-fonts nao estiver disponivel
_BASE14 = {
    "regular":     "helv",
    "bold":        "hebo",
    "italic":      "heit",
    "bold_italic": "hebi",
}


def _pick_font_variant(span: TextSpan) -> str:
    """Retorna o nome da variante de fonte (chave do dicionario interno)."""
    flags = span.flags
    is_bold   = bool(flags & 16) or "bold"    in span.font.lower() or "-bd" in span.font.lower()
    is_italic = bool(flags & 2)  or "italic"  in span.font.lower() or "oblique" in span.font.lower()
    if is_bold and is_italic:
        return "bold_italic"
    if is_bold:
        return "bold"
    if is_italic:
        return "italic"
    return "regular"


def _variant_to_fontname(variant: str) -> str:
    """Converte variante para o nome de fonte a usar no insert_textbox."""
    if _HAS_NOTO:
        return {
            "regular":     _NOTO_REGULAR,
            "bold":        _NOTO_BOLD,
            "italic":      _NOTO_ITALIC,
            "bold_italic": _NOTO_BOLD_ITALIC,
        }[variant]
    return _BASE14[variant]


def _int_color_to_rgb(c: int) -> Tuple[float, float, float]:
    r = ((c >> 16) & 0xFF) / 255.0
    g = ((c >> 8)  & 0xFF) / 255.0
    b = (c & 0xFF)          / 255.0
    return (r, g, b)


def _register_noto_fonts(doc: pymupdf.Document) -> None:
    """
    Pre-registra as 4 variantes NotoSans no documento uma unica vez.
    PyMuPDF deduplica automaticamente por xref; chamadas extras sao no-op.
    """
    if not _HAS_NOTO:
        return
    # Registrar em todas as paginas seria caro; PyMuPDF aceita registrar
    # numa pagina e referenciar nas demais desde que o fontname seja igual.
    # Usamos a pagina 0 como ancora; se o doc for vazio, nao faz nada.
    if len(doc) == 0:
        return
    page0 = doc[0]
    for fname, buf in _FONT_BUFFERS.items():
        try:
            page0.insert_font(fontname=fname, fontbuffer=buf)
        except Exception as e:  # noqa: BLE001
            log.debug("Nao foi possivel pre-registrar fonte %s: %s", fname, e)


def write_translated_pdf(
    input_pdf: str,
    output_pdf: str,
    spans: List[TextSpan],
    translations: List[str],
) -> None:
    """
    Aplica `translations[i]` no lugar de `spans[i].text` no PDF de saida.

    Args:
        input_pdf:    caminho do PDF original.
        output_pdf:   caminho onde salvar o PDF traduzido.
        spans:        lista produzida por extractor.extract_spans().
        translations: lista paralela com o texto traduzido de cada span.
    """
    if len(spans) != len(translations):
        raise ValueError(
            f"Spans ({len(spans)}) e translations ({len(translations)}) "
            "precisam ter o mesmo tamanho."
        )

    doc = pymupdf.open(input_pdf)

    try:
        # Registra fontes Noto uma vez antes de percorrer as paginas
        _register_noto_fonts(doc)

        # Agrupa spans por pagina
        by_page: dict[int, list[tuple[TextSpan, str]]] = {}
        for span, translation in zip(spans, translations):
            by_page.setdefault(span.page, []).append((span, translation))

        for page_idx, items in by_page.items():
            page = doc[page_idx]

            # Garante que as fontes Noto estao registradas nesta pagina
            if _HAS_NOTO:
                for fname, buf in _FONT_BUFFERS.items():
                    try:
                        page.insert_font(fontname=fname, fontbuffer=buf)
                    except Exception:  # noqa: BLE001
                        pass  # ja registrada ou erro nao-critico

            # 1) Cobrir o texto original com retangulo branco
            for span, translation in items:
                if translation == span.text:
                    continue
                rect = pymupdf.Rect(span.bbox)
                rect = pymupdf.Rect(
                    rect.x0 - 0.5, rect.y0 - 0.5,
                    rect.x1 + 0.5, rect.y1 + 0.5,
                )
                page.draw_rect(rect, color=None, fill=(1, 1, 1), overlay=True)

            # 2) Escrever texto traduzido
            for span, translation in items:
                if translation == span.text:
                    continue

                rect      = pymupdf.Rect(span.bbox)
                variant   = _pick_font_variant(span)
                fontname  = _variant_to_fontname(variant)
                color     = _int_color_to_rgb(span.color)
                font_size = span.size

                # Draw rect: usa o espaco disponivel ate o fim da linha,
                # nunca ultrapassando a margem direita da pagina.
                # Isso resolve o Problema 1 (expansao horizontal arbitraria
                # que causava overflow fora da pagina).
                page_w    = span.page_w if span.page_w > 0 else page.rect.width
                line_x1   = span.line_x1 if span.line_x1 > rect.x1 else rect.x1
                right_cap = page_w - 30          # margem de seguranca de 30pt
                draw_right = min(line_x1 + 5, right_cap)
                # Garante ao menos a largura original do span
                draw_right = max(draw_right, rect.x1)

                draw_rect = pymupdf.Rect(
                    rect.x0,
                    rect.y0 - 1.0,
                    draw_right,
                    rect.y1 + 2.0,
                )

                # Reducao de fonte em 3 passos rapidos antes de iterar fino:
                # tenta 90%, 80%, 70% do tamanho original, depois -0.5pt ate 6pt.
                inserted = -1
                size_candidates = [
                    font_size,
                    round(font_size * 0.90, 1),
                    round(font_size * 0.80, 1),
                    round(font_size * 0.70, 1),
                ]
                for fs in size_candidates:
                    if fs < 6.0:
                        break
                    inserted = page.insert_textbox(
                        draw_rect, translation,
                        fontname=fontname, fontsize=fs,
                        color=color, align=0, overlay=True,
                    )
                    if inserted >= 0:
                        font_size = fs
                        break

                # Se ainda nao coube, descida fina de 0.5pt ate 6pt
                if inserted < 0:
                    font_size = round(size_candidates[-1], 1)
                    while font_size >= 6.0:
                        font_size -= 0.5
                        inserted = page.insert_textbox(
                            draw_rect, translation,
                            fontname=fontname, fontsize=font_size,
                            color=color, align=0, overlay=True,
                        )
                        if inserted >= 0:
                            break

                if inserted < 0:
                    # Ultimo recurso: 6pt forcado (melhor que 4pt ilegivel)
                    page.insert_textbox(
                        draw_rect, translation,
                        fontname=fontname, fontsize=6.0,
                        color=color, align=0, overlay=True,
                    )
                    log.warning(
                        "Span pagina %s nao coube nem em 6pt: %r",
                        page_idx,
                        translation[:60],
                    )

        doc.save(output_pdf, garbage=4, deflate=True)
    finally:
        doc.close()
