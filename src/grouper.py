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


# Gap horizontal minimo para considerar separacao de coluna de tabela:
# gap > font_size * _COLUMN_GAP_RATIO -> celulas separadas.
#
# Valor 1.5 e suficiente para detectar separacoes de coluna reais (tipicamente
# 15-50pt para fonte 10-11pt) enquanto ignora espacos entre palavras (~2-4pt).
# Valor 2.0 era alto demais: em tabelas com colunas estreitas (gap ~20pt,
# threshold 22pt para fonte 11pt) deixava de separar celulas adjacentes,
# causando texto misturado de duas colunas no mesmo bloco de traducao.
# Validado: ratio 1.5 separa corretamente o caso critico (gap 20.2pt, 11pt
# font -> threshold 16.5pt) sem falsos positivos em texto corrido.
_COLUMN_GAP_RATIO = 1.5
# Tolerancia de y para determinar "mesma linha visual" entre spans:
_SAME_ROW_Y_TOL = 2.0  # pt


def _split_by_columns(
    spans: List[TextSpan],
    v_lines: "list[float] | None" = None,
) -> List[List[TextSpan]]:
    """
    Divide spans de um bloco em grupos de colunas quando estao em celulas
    de tabela distintas no mesmo y visual.

    DOIS sinais de separacao (qualquer um basta):

    1. **Gap horizontal grande** entre spans consecutivos:
       gap > font_size * _COLUMN_GAP_RATIO. Cobre tabelas com colunas bem
       espacadas, sem necessidade de bordas visiveis.

    2. **Borda vertical detectada NO MEIO do gap** (Sessao #10):
       se v_lines for fornecida e existe alguma borda em (prev.x1, curr.x0),
       os spans pertencem a celulas diferentes mesmo com gap pequeno.
       Cobre tabelas com colunas estreitas e celulas adjacentes coladas
       (caso "Distribution: Novo Nordisk - E AFRY BR - E" do RFQ Novo Nordisk:
       gaps de 10-12pt < threshold 13.5pt, mas bordas em 206.5 e 277.4
       confirmam que sao 3 celulas distintas).

    Pre-condicao para checar colunas: todos os spans devem compartilhar o
    mesmo y-centro (diferenca < _SAME_ROW_Y_TOL). Se ha multiplas linhas
    visuais (paragrafo real), nao divide.

    Args:
        spans: spans de um TextBlock candidato (ja pertencentes ao mesmo
               bloco do PyMuPDF).
        v_lines: lista ordenada de x-coords de bordas verticais da pagina
                 (como retornada por writer._get_page_vertical_lines). Se
                 None, so usa o sinal de gap horizontal (comportamento legacy).

    Returns:
        Lista de sub-grupos. Tamanho 1 se nenhum split aconteceu.

    Genericidade: nao detecta "tabela" especificamente. Funciona em qualquer
    layout onde celulas estao no mesmo y visual e ou (a) ha gap suficiente
    ou (b) ha linha divisora visivel no PDF original.
    """
    if len(spans) <= 1:
        return [spans]

    # Calcular y-centro de cada line_idx
    line_ys: Dict[int, List[float]] = {}
    for s in spans:
        line_ys.setdefault(s.line, []).append((s.bbox[1] + s.bbox[3]) / 2.0)
    line_centers = {li: sum(ys) / len(ys) for li, ys in line_ys.items()}

    # Se ha mais de uma linha e elas tem y distintos -> paragrafo, nao dividir
    sorted_centers = sorted(line_centers.values())
    for i in range(1, len(sorted_centers)):
        if sorted_centers[i] - sorted_centers[i - 1] > _SAME_ROW_Y_TOL:
            return [spans]  # paragrafo multi-linha

    # Todos os spans estao no mesmo y visual (linha de tabela ou span unico):
    # ordenar por x0 e procurar gaps de coluna OU bordas verticais.
    sorted_spans = sorted(spans, key=lambda s: s.bbox[0])
    avg_size = sum(s.size for s in spans) / len(spans)
    gap_threshold = avg_size * _COLUMN_GAP_RATIO

    groups: List[List[TextSpan]] = [[sorted_spans[0]]]
    for i in range(1, len(sorted_spans)):
        prev = sorted_spans[i - 1]
        curr = sorted_spans[i]
        gap = curr.bbox[0] - prev.bbox[2]

        # Sinal A: gap horizontal suficientemente grande
        cond_gap = gap > gap_threshold

        # Sinal B: borda vertical entre os dois spans (estritamente no gap)
        cond_border = False
        if v_lines and gap > 0:
            cond_border = any(prev.bbox[2] < v < curr.bbox[0] for v in v_lines)

        if cond_gap or cond_border:
            groups.append([])
        groups[-1].append(curr)

    return groups if len(groups) > 1 else [spans]


def _dominant_span(spans: List[TextSpan]) -> TextSpan:
    """
    Retorna o span 'dominante' do bloco para fins de estilo.
    Criterio: maior tamanho de fonte; em caso de empate, o primeiro da lista.
    """
    return max(spans, key=lambda s: s.size)


def group_into_blocks(
    spans: List[TextSpan],
    v_lines_by_page: "Dict[int, list[float]] | None" = None,
) -> List[TextBlock]:
    """
    Agrupa uma lista plana de TextSpan em TextBlocks por (page, block_idx).

    A ordem dos blocos na lista de saida reflete a ordem de leitura do PDF
    (pagina crescente, depois indice de bloco crescente).

    Args:
        spans: lista plana de spans extraidos pelo extractor.
        v_lines_by_page: opcional, mapa pagina -> lista de x-coords de bordas
                         verticais detectadas (de writer._get_page_vertical_lines).
                         Quando fornecido, _split_by_columns usa bordas como sinal
                         de separacao de celulas alem do gap horizontal. Sem isso,
                         comportamento legacy (so gap horizontal).
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

        # Bordas verticais desta pagina (se fornecidas) para melhorar deteccao
        # de celulas adjacentes coladas (caso "Distribution: Novo Nordisk - E
        # AFRY BR - E" do RFQ Novo Nordisk).
        page_v_lines = (v_lines_by_page or {}).get(page)

        # Dividir em sub-blocos de coluna se necessario (celulas de tabela)
        col_groups = _split_by_columns(block_spans, v_lines=page_v_lines)

        for col_spans in col_groups:
            dom = _dominant_span(col_spans)
            blocks.append(TextBlock(
                page=page,
                block_idx=block_idx,
                spans=col_spans,
                text=_build_block_text(col_spans),
                bbox=_union_bbox(col_spans),
                font=dom.font,
                size=dom.size,
                color=dom.color,
                flags=dom.flags,
                page_w=col_spans[0].page_w,
            ))

    return blocks
