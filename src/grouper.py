"""
Grouper: agrupa spans em blocos logicos (paragrafos) para traducao coerente.

Problema 3 (Fase 1):
- Ao traduzir span-a-span, cada fragmento e traduzido isoladamente, gerando
  texto descontinuo e lacunas entre os segmentos.
- Solucao: agrupar spans que pertencem ao mesmo bloco (page, block_idx) em um
  TextBlock e traduzir o bloco inteiro de uma vez como paragrafo coerente.

PyMuPDF ja separa o texto em blocos logicos ao extrair com get_text("dict").
Cada bloco corresponde a um paragrafo ou elemento textual coeso. Usamos essa
estrutura como unidade minima de traducao.

Limitacoes conhecidas desta fase:
- Blocos com spans de estilos mistos (bold+regular na mesma linha) perdem a
  diferenciacao de estilo intra-bloco: o bloco inteiro usa o estilo do span
  dominante (maior fonte, ou primeiro em caso de empate).
- Layout multi-coluna: o bbox do bloco pode ser incorreto se o PDF nao tiver
  blocos explicitamente separados por coluna. Tratamento em Problema 4.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .extractor import TextSpan


@dataclass
class TextBlock:
    """Unidade de traducao: um paragrafo ou elemento textual coeso."""
    page: int
    block_idx: int
    spans: List[TextSpan]
    text: str                                    # texto corrido do bloco
    bbox: Tuple[float, float, float, float]      # union bbox de todos os spans
    font: str                                    # fonte do span dominante
    size: float                                  # tamanho do span dominante
    color: int                                   # cor do span dominante
    flags: int                                   # flags do span dominante
    page_w: float                                # largura da pagina


def _union_bbox(spans: List[TextSpan]) -> Tuple[float, float, float, float]:
    """Retorna o bbox que envolve todos os spans do bloco."""
    x0 = min(s.bbox[0] for s in spans)
    y0 = min(s.bbox[1] for s in spans)
    x1 = max(s.bbox[2] for s in spans)
    y1 = max(s.bbox[3] for s in spans)
    return (x0, y0, x1, y1)


def _build_block_text(spans: List[TextSpan]) -> str:
    """
    Concatena os spans de um bloco em texto estruturado.

    Estrategia de juncao entre linhas do bloco:
    - Dentro de cada linha (mesmo line_idx): une os spans com espaco se necessario.
    - Entre linhas diferentes: usa \n se as linhas estiverem em posicoes y
      distintas (linhas visuais reais), ou espaco se compartilharem a mesma
      posicao y (campos tabulados que o PyMuPDF split em line_idx separados,
      como "1." e "INTRODUCTION ......" num TOC).

    Limiar de separacao: 2pt. Se |y_centro_A - y_centro_B| < 2pt, as duas
    'linhas' estao na mesma linha visual e sao unidas com espaco.

    Google Translate preserva \n, entao blocos com multiplas linhas reais
    (como listas ou titulos em duas linhas) continuam separados apos a traducao.
    """
    if not spans:
        return ""

    # Agrupar por linha (line_idx do PyMuPDF)
    lines: Dict[int, List[TextSpan]] = {}
    for s in spans:
        lines.setdefault(s.line, []).append(s)

    # Para cada linha: calcular y-centro e texto
    line_data: List[Tuple[float, str]] = []
    for line_idx in sorted(lines):
        line_spans = sorted(lines[line_idx], key=lambda s: s.span)
        parts: List[str] = []
        for i, s in enumerate(line_spans):
            if i == 0:
                parts.append(s.text)
            else:
                prev = parts[-1] if parts else ""
                if prev and not prev[-1].isspace() and s.text and not s.text[0].isspace():
                    parts.append(" " + s.text)
                else:
                    parts.append(s.text)
        line_text = "".join(parts).strip()
        if line_text:
            # y-centro da linha: media dos centros verticais dos spans
            ys = [(s.bbox[1] + s.bbox[3]) / 2.0 for s in line_spans]
            y_center = sum(ys) / len(ys)
            line_data.append((y_center, line_text))

    if not line_data:
        return ""

    # Construir texto final: espaco se mesma linha visual, \n se linha diferente
    _SAME_LINE_THRESHOLD = 2.0  # pt
    result_parts = [line_data[0][1]]
    for i in range(1, len(line_data)):
        prev_y = line_data[i - 1][0]
        curr_y = line_data[i][0]
        if abs(curr_y - prev_y) < _SAME_LINE_THRESHOLD:
            # Mesma posicao y: campos tabulados na mesma linha visual
            sep = "" if result_parts[-1].endswith(" ") or line_data[i][1].startswith(" ") else " "
            result_parts.append(sep + line_data[i][1])
        else:
            # Linha visual diferente: preservar quebra
            result_parts.append("\n" + line_data[i][1])

    return "".join(result_parts)


def _dominant_span(spans: List[TextSpan]) -> TextSpan:
    """
    Retorna o span 'dominante' do bloco para fins de estilo.
    Criterio: maior tamanho de fonte; em caso de empate, o primeiro da lista.
    """
    return max(spans, key=lambda s: s.size)


def group_into_blocks(spans: List[TextSpan]) -> List[TextBlock]:
    """
    Agrupa uma lista plana de TextSpan em TextBlocks por (page, block_idx).

    A ordem dos blocos na lista de saida reflete a ordem de leitura do PDF
    (pagina crescente, depois indice de bloco crescente).
    """
    if not spans:
        return []

    groups: Dict[Tuple[int, int], List[TextSpan]] = {}
    for s in spans:
        key = (s.page, s.block)
        groups.setdefault(key, []).append(s)

    blocks: List[TextBlock] = []
    for (page, block_idx) in sorted(groups):
        block_spans = sorted(groups[(page, block_idx)], key=lambda s: (s.line, s.span))
        dom = _dominant_span(block_spans)

        blocks.append(TextBlock(
            page=page,
            block_idx=block_idx,
            spans=block_spans,
            text=_build_block_text(block_spans),
            bbox=_union_bbox(block_spans),
            font=dom.font,
            size=dom.size,
            color=dom.color,
            flags=dom.flags,
            page_w=block_spans[0].page_w,
        ))

    return blocks
