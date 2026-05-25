# PROGRESSO — Tradutor PDF

> **Save state vivo do projeto.** Atualizado a cada sessão de trabalho.
> Para a visão completa do plano, ver [`briefing-tradutor-pdf.md`](briefing-tradutor-pdf.md).
> Para retomar em outra máquina, ver a seção [**"Prompt de retomada"**](#prompt-de-retomada) no final.

---

## Onde estamos agora

**Fase atual:** Fase 1 — Qualidade de tradução e robustez. **Os 5 problemas do briefing estão resolvidos no básico**, MAS PDF nativo **ainda NÃO está 100% pronto pra produção**. Resta validação em PDFs variados e correção dos casos que aparecerem.

**Última sessão:** 2026-05-24 (Sessão #9 — Opus). Refinamento do right-cap por bordas verticais. Discussão honesta com Miguel: identificamos que pular para "PDF escaneado" agora seria prematuro.

**Limitações conhecidas em PDF nativo (precisam ser endereçadas ANTES de seguir):**

1. ~~**Grouper combina células adjacentes coladas**~~ — ✅ **RESOLVIDO na Sessão #10**. `_split_by_columns` agora aceita `v_lines` opcional e usa bordas verticais detectadas como sinal adicional de separação (qualquer borda no gap entre 2 spans no mesmo y → split). `pipeline.py` calcula bordas por página antes de agrupar. 9/9 testes passando (`tests/test_grouper_borders.py`). Caso AFRY do `document_pdf (1).pdf` validado: 1 bloco → 3 blocos separados. Identificados +17 casos similares no mesmo PDF que também foram corrigidos.

2. **Caracteres especiais aparecem como □ (glifos ausentes)** — alguns bullets e símbolos específicos do PDF original não têm mapeamento direto na NotoSans (pymupdf-fonts). Visto em listas com `❑` na página 7 do `document_pdf (1)_pt.pdf`.

3. **Tradução grande não cabe em célula estreita** — em tabelas com colunas estreitas, mesmo reduzindo fonte a 6pt o `insert_textbox` pode falhar (retorna -1, não escreve nada). Resultado: célula traduzida fica vazia. Visto em casos extremos com mock pesado.

4. **Tabelas sem bordas visíveis** — right-cap depende de vizinhos TextBlock OU bordas verticais detectadas via `get_drawings`. Tabelas alinhadas por espaços (sem linhas divisórias visíveis) e com células vazias caem em terra de ninguém.

5. **Sumário (TOC) com dot leaders inconsistentes** — TOC tem padrão `numerador + título + ............ + número de página`. No PDF original esses três (título + dots + número) vivem num único span gerado pelo Word com dots calculados pra preencher exatamente o espaço. Pipeline manda tudo pro Google que devolve quantidade arbitrária de dots; resultado pode ter dots cortados, espaçados, ou colando no número da página. Numerador também aparece com retângulo branco visível ao redor (resíduo do cover do span original que era curto). Identificado na Sessão #9 inspecionando bloco 12 do `document_pdf.pdf` (TOC página 2). Possível solução: detectar padrão `texto + dots + número`, traduzir só o título, regerar dots para preencher espaço calculado. Decisão Miguel: postergar; pode ser irrelevante em PDFs sem TOC.

6. **Suite de testes real é mínima** — só validamos nos 2 PDFs do Miguel (`document_pdf.pdf` 42p e `document_pdf (1).pdf` 25p). Falta bateria com PDFs variados da internet.

**Próximo bloco de trabalho (ORDEM CORRIGIDA):**

1. **PRIORIDADE 1: Suite de testes com PDFs variados da internet** — baixar 8-12 PDFs diversos (relatórios públicos, artigos científicos, manuais técnicos, formulários, faturas, contratos), rodar no pipeline com Google Translate real, coletar falhas, catalogar.
2. **PRIORIDADE 2: Corrigir os casos que aparecerem** — provavelmente refinamentos no grouper, fontes, e right-cap. Cada correção precisa de teste unitário pra travar regressão.
3. **PRIORIDADE 3: Recuperação de jobs** — persistência além do browser fechado, histórico de jobs por usuário, expiração após X horas. UX importante quando PDFs grandes demoram.

**Detecção/tradução de PDF escaneado:** **postergada para depois do site estar rodando em produção** (decisão do Miguel na Sessão #9). Só faz sentido como evolução de produto, não como pré-requisito técnico. Ver Fase 4 abaixo.

Modelo sugerido: Opus para estratégia de testes (P1) e diagnóstico das falhas (P2 — heurísticas no grouper); Sonnet para correções mecânicas e implementação de jobs.

---

## Decisões tomadas (que diferem ou refinam o briefing)

| Decisão | Briefing original | Decisão tomada | Por quê |
|---|---|---|---|
| Tradutor da Fase 0 | Claude ou DeepL | **Google Translate (gratuito) via `deep-translator`**, com fallback automático para MyMemory | Miguel pediu opção gratuita inicialmente. Sem API key, sem custo. Trocar por Claude/DeepL depois é só plugar novo provider na interface `TranslatorProvider`. |
| Forma da Fase 0 | CLI mínima de fim de semana | **Aplicação fullstack desde o início** (FastAPI + HTML/Tailwind) | Miguel quer um piloto já com cara de produto, escalável para multi-idioma e com hooks para monetização. CLI fica como bônus (`cli.py`). |
| 5 problemas técnicos do briefing | Atacar todos progressivamente | **Adiados para iterações pós-Fase 0** (tradução crua primeiro) | Decisão explícita do Miguel. Validar pipeline básico antes de polir. |
| Persistência de progresso entre máquinas | Não previsto | **Este arquivo (`PROGRESSO.md`) + briefing versionados no git** | Cowork guarda sessões localmente; a portabilidade real vem do git + docs. |
| Recuperação de jobs | Não previsto | **Jobs devem persistir para o usuário mesmo se fechar o browser** — arquivo fica salvo temporariamente na conta; job roda em background; usuário pode recuperar pelo histórico de jobs. | Miguel: "demorou pra traduzir, é importante ter forma de recuperar". Implementar em Fase 2/3 quando houver auth real. |
| Modelo de cobrança | Créditos ou planos | **Modelo de créditos** — vender créditos em pacotes fixos; cada tradução consome 1 crédito; crédito só é descontado se a tradução completar sem erros. | Miguel definiu. Implementar quando chegar em Fase 3 (billing real). |
| Detecção de PDF escaneado | Mensagem clara ou OCR | **Pré-análise obrigatória antes de traduzir** — detectar se PDF é texto puro ou imagem; negar tradução se for escaneado (ou raster), com mensagem clara ao usuário. OCR (Tesseract) como opção futura. | Miguel levantou. Já existe warning no pipeline; falta bloquear na API e mostrar erro amigável na UI. Implementar na Fase 2. |

---

## Orientação: Sonnet vs Opus

| Tarefa | Modelo recomendado | Motivo |
|---|---|---|
| Problema 1 — expansão de texto (ajuste de bbox, font-size) | **Sonnet** | Engenharia direta, sem ambiguidade |
| Problema 2 — fontes Unicode | ~~Sonnet~~ ✅ concluído | — |
| Problema 3 — agrupamento de parágrafos | **Sonnet** (início) → avaliar Opus | Heurística moderada; se a detecção de blocos lógicos ficar complexa, escalar para Opus |
| Problema 4 — cabeçalhos/rodapés/tabelas | ~~Opus~~ ✅ concluído | Right-cap dinâmico por vizinhos resolveu de forma genérica |
| Problema 5 — glossário técnico | ~~Sonnet~~ ✅ concluído | — |
| Fase 2 — suite de testes, detecção de PDF escaneado | **Opus** | Decisões de estratégia de testes e edge cases |
| Arquitetura de produto (Fase 3 — decisão A/B/C) | **Opus** | Decisão estratégica de alto impacto |
| Auth + Billing real | **Sonnet** | Implementação padrão |

**Resumo:** Sessão #8 (Opus) fechou Fase 1. Daqui em diante: Sonnet para Fase 2 implementação rotineira; Opus para decisões de teste/edge cases e arquitetura (Fase 3).

---

## Checklist de implementação

### Fase 0 — Piloto fullstack

#### Estrutura e fundação
- [x] Estrutura de pastas (`src/`, `app/`, `tests/`, `examples/`)
- [x] `requirements.txt` (pymupdf, deep-translator, fastapi, uvicorn)
- [x] `.env.example` (placeholders para Anthropic, DeepL, Stripe, Mercado Pago)
- [x] `.gitignore`
- [x] `pyproject.toml`
- [x] `setup_git.ps1` para configurar git localmente
- [x] `PROGRESSO.md` (este arquivo)

#### Pipeline core
- [x] `src/extractor.py` — extrai spans com PyMuPDF (texto + bbox + fonte + cor)
- [x] `src/translator.py` — wrapper de provedores (Google, MyMemory) com cache e fallback automático
- [x] `src/writer.py` — apaga texto original e reescreve traduzido na mesma bbox, com redução automática de tamanho se não couber
- [x] `src/pipeline.py` — orquestrador com callback de progresso
- [x] `cli.py` — entry point CLI

#### Backend web (FastAPI)
- [x] `app/main.py` — instância FastAPI, rotas, mount de templates
- [x] `app/jobs.py` — gerenciamento de jobs em memória, thread-safe
- [x] `app/auth.py` — placeholder (todos os requests passam por enquanto)
- [x] `app/billing.py` — placeholder com catálogo de planos (Free/Starter/Pro/Business)
- [x] `app/quotas.py` — placeholder (rate-limit por IP/usuário)
- [x] Endpoints: `POST /api/translate`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/download`, `GET /api/languages`, `GET /api/plans`, `GET /healthz`

#### Frontend
- [x] `app/templates/index.html` — Tailwind via CDN, drag-and-drop, seletor de idiomas, barra de progresso, download
- [x] Botões inertes "Entrar" e "Planos" reservados para o futuro

#### Testes e validação
- [x] Pipeline validado end-to-end com translator MOCK (sandbox bloqueia rede externa) sobre `document_pdf (1).pdf` (25 págs, 1512 spans em ~4s)
- [x] Inspecionar visualmente o output (PNG da página 0 — layout, logos, tabelas preservados; texto traduzido aparece com prefixo `[PT]`)
- [x] `tests/test_extractor.py` — teste mínimo de extração
- [x] `README.md` final com instruções
- [x] **✅ VALIDADO por Miguel (Sessão #2):** traduziu `document_pdf.pdf` (42 págs) com Google Translate real. Layout, logos, tabelas preservados. Problema visível: "?" em alguns caracteres especiais (Problema 2 — fontes, próxima fase).

### Fases futuras (do briefing)

#### Fase 1 — atacar os 5 problemas (ATUAL)
- [x] **Problema 2: Fontes sem charset Unicode** — ✅ resolvido (Sessão #2/3). NotoSans via `pymupdf-fonts` elimina "?" de acentos. Fix adicional no `translator.py`: protect/restore de `–`, `•`, `'`, `"`, `©`, `°` etc. antes de enviar ao Google Translate (que os malhava para `?`). Spans com apenas símbolos/números pulam a tradução.
- [x] **Problema 1: Expansão de texto** — ✅ resolvido (Sessão #4). `extractor.py`: adicionado `line_x1` e `page_w` ao TextSpan. `writer.py`: draw_rect usa espaço real da linha + cap na margem da página (30pt). Redução de fonte em 3 passos (90/80/70%) antes da descida fina. Mínimo de 6pt (era 4pt). 229 overflows → 0.
- [x] **Problema 3: Granularidade de blocos** — ✅ resolvido (Sessão #5/6). Novo módulo `src/grouper.py` agrupa spans em TextBlocks por (page, block_idx). `pipeline.py` traduz por bloco (2.2× menos chamadas ao tradutor). `writer.py` escreve texto traduzido no bbox do bloco inteiro — elimina os grandes espaços vazios entre spans. Fix de linha visual: spans no mesmo y são unidos com espaço (campos tabulados); linhas em y diferente usam \n. Fix cosmético (Sessão #6): `_CELL_PADDING_LEFT = 2.0pt` adicionado ao draw_rect — afasta o texto da borda vertical de células de tabela, eliminando o artefato visual de "texto cortado" pela linha divisória. Validado com PDF real (25 págs, 1049 blocos).
- [x] **Problema 4: Tabelas / cabeçalhos / rodapés** — ✅ TOTALMENTE resolvido. (a) Sessão #5: `_split_by_columns()` detecta células de tabela por gap horizontal. (b) Sessão #7: detecção de bordas verticais via `page.get_drawings()` para posicionamento do x-inicial. (c) Sessão #8: `_compute_right_cap()` — regra universal "nenhum bloco invade x-range de outro bloco no mesmo y" (cap por vizinho TextBlock). (d) **Sessão #9: extensão do right-cap com cap por borda vertical** — quando célula vizinha está vazia (sem TextBlock), o cap usa a próxima borda vertical detectada como limite. 19/19 testes unitários passando (`tests/test_writer_neighbor_cap.py`). Genérico: independe de detectar "tabela" ou "rodapé" — aplica-se a qualquer PDF nativo (tabelas, multi-coluna, formulários, RFQs).
- [x] **Problema 5: Glossário técnico** — ✅ resolvido (Sessão #6). Novo módulo `src/glossary.py` com classe `Glossary`: protect/restore de termos via placeholders `__GLOSS0__` antes de enviar ao provedor. `TranslationService` recebe `glossary` opcional. `pipeline.py` aceita `glossary_path` opcional. `app/glossaries.py`: `GlossaryStore` com persistência em JSON (`app/storage/glossaries/`). 5 endpoints REST (`POST/GET/PUT/DELETE /api/glossaries`). UI: dropdown para selecionar glossário + modal para criar/remover glossários com textarea `origem = destino`.

#### Fase 2 — robustez (ordem corrigida após discussão Sessão #9)
- [ ] **P1: Suite de testes pré-produção** — baixar 8-12 PDFs variados (relatórios públicos, artigos científicos, manuais técnicos, formulários, faturas, contratos) e rodar no pipeline com Google Translate real. Catalogar TODAS as falhas observadas. Este passo é o que vai mostrar o que ainda quebra em PDF nativo — sem ele, qualquer afirmação de "está pronto" é otimismo.
- [ ] **P2: Corrigir falhas catalogadas** — provável foco:
  - ~~`grouper.py`: heurística para detectar quando duas células adjacentes coladas foram combinadas em UM TextBlock~~ — ✅ Sessão #10.
  - `writer.py`: tratamento para glifos ausentes na NotoSans (bullets como ❑ que viram □).
  - `writer.py`: comportamento defensivo quando `insert_textbox` falha mesmo em 6pt (célula muito estreita).
  - `writer.py`: estratégia para tabelas sem bordas visíveis.
  - `writer.py` ou novo módulo `toc.py`: tratamento de sumário (TOC) — detectar padrão "título + dots + número de página" e regerar dots para preencher exatamente o espaço calculado entre título traduzido e número da página.
  - Cada correção com teste unitário travando regressão.
- [ ] **P3: Recuperação de jobs** — job persiste mesmo se usuário fechar o browser; histórico de jobs acessível; arquivo fica disponível por X horas após conclusão.
- [ ] Comparação visual lado-a-lado (antes/depois por página)
- [ ] Suporte a múltiplos pares de idioma testados

**Detecção de PDF escaneado: NÃO está na Fase 2.** Decisão do Miguel (Sessão #9): só implementar depois do site estar rodando em produção. Movido para Fase 4 (PDFs escaneados / OCR), tratado como evolução de produto.

#### Fase 3 — produto
- [ ] Decidir entre Caminho A (web app self-service), B (SaaS B2B) ou C (ferramenta + serviço)
- [ ] Auth real
- [ ] **Modelo de créditos** — vender créditos em pacotes fixos; 1 crédito por tradução; desconto só após conclusão sem erros.
- [ ] Billing real (Stripe ou Mercado Pago)
- [ ] Database (Postgres) para usuários, jobs, glossários, saldo de créditos

#### Fase 4 — PDFs escaneados (produto consolidado)
- [ ] **OCR + tradução de PDFs raster** — quando o site estiver maduro em texto puro, adicionar produto separado (ou modo premium) que recebe PDF escaneado (imagem), faz OCR (Tesseract ou API), reconstrói o documento como texto e traduz preservando layout. Produto distinto do tradutor atual, que só funciona com PDFs de texto nativo.

---

## Arquitetura atual (Fase 0)

```
Frontend (HTML+Tailwind)
   │  upload PDF + idiomas
   ▼
POST /api/translate ──► cria Job em memória ──► dispara pipeline em background task
                                                       │
                                                       ▼
                                          src/pipeline.translate_pdf()
                                                       │
                                            ┌──────────┼──────────┐
                                            ▼          ▼          ▼
                                       extractor   translator   writer
                                       (PyMuPDF)   (Google)    (PyMuPDF)
                                            │          │          │
                                            └──────────┴──────────┘
                                                       │
                                                       ▼
                                                   Job atualiza status
   ▲                                                    │
GET /api/jobs/{id} ◄────────────────────────────────────┘
   │
   ▼
GET /api/jobs/{id}/download  (PDF traduzido)
```

**Pontos de extensão prontos para o futuro:**
- Novo provider de tradução: adicionar classe que implementa `TranslatorProvider` em `src/translator.py`
- Novo par de idiomas: adicionar entrada em `SUPPORTED_LANGUAGES`
- Auth: implementar `app/auth.py` (estrutura já pronta como middleware)
- Billing: implementar `app/billing.py` (interface esperada por `app/quotas.py`)
- Persistência: trocar dict em memória de `app/jobs.py` por Postgres+Redis sem mexer no resto

---

## Como continuar em outra máquina

1. **Clonar o repo:**
   ```
   git clone https://github.com/SEU_USUARIO/tradutor-pdf.git
   cd tradutor-pdf
   ```

2. **Instalar dependências:**
   ```
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1     # Windows
   # source .venv/bin/activate       # Linux/Mac
   pip install -r requirements.txt
   ```

3. **Abrir o Cowork na pasta** (ou Claude Code, ou outro cliente).

4. **Colar o [Prompt de retomada](#prompt-de-retomada)** abaixo na nova sessão.

5. **Conferir este arquivo** — ele tem o estado mais recente do projeto.

---

## Prompt de retomada

> Cole o bloco abaixo numa nova sessão do Cowork (Opus recomendado) para retomar exatamente de onde paramos.

```
Estou retomando o projeto Tradutor PDF (preservacao de layout).
Sou Miguel, Automation Specialist.

=== LEIA ANTES DE QUALQUER COISA ===
1. Leia PROGRESSO.md inteiro — ele tem o estado real do projeto.
2. Leia src/writer.py, src/grouper.py, src/translator.py — os tres arquivos
   com mudancas recentes.
3. Confirme comigo qual e o proximo passo ANTES de codificar qualquer coisa.

=== CONTEXTO TECNICO (estado atual — Sessao #7) ===

Stack: FastAPI + PyMuPDF + deep-translator (Google/MyMemory). Windows, Python 3.11.
Pasta do projeto: C:\Users\migms\Documents\Tradutor_PDF

Pipeline (src/):
  extractor.py  -> extrai TextSpan (page, block, line, span, bbox, font, size, color, flags, page_w, line_x1)
  grouper.py    -> agrupa spans em TextBlock por (page, block_idx); detecta celulas de tabela
  translator.py -> TranslationService com cache, fallback MyMemory, protect/restore de chars especiais e glossario
  glossary.py   -> Glossary com protect/restore de termos via placeholders __GLOSS0__
  pipeline.py   -> orquestrador; aceita glossary_path opcional
  writer.py     -> apaga texto original (draw_rect branco), reescreve traduzido; deteccao de bordas de tabela

Backend (app/):
  main.py       -> FastAPI; endpoints de traducao, jobs, glossarios
  jobs.py       -> JobStore em memoria, thread-safe
  glossaries.py -> GlossaryStore com persistencia JSON em app/storage/glossaries/

Frontend: app/templates/index.html (Tailwind CDN, drag-and-drop, progress, download, modal de glossarios)

=== OS 5 PROBLEMAS DA FASE 1 — STATUS ===

Problema 1 (expansao de texto): RESOLVIDO.
  - writer.py usa draw_rect com espaco real da linha (line_x1 - bx0), cap em page_w - 30pt.
  - Reducao de fonte em 3 passos (90/80/70%) + descida fina; minimo 6pt.
  - Resultado: 229 overflows -> 0.

Problema 2 (fontes Unicode): RESOLVIDO.
  - NotoSans (via pymupdf-fonts) substitui fontes base14 Latin-1.
  - writer.py detecta bold/italic pelo campo flags e usa variante certa.
  - translator.py protege –, •, ', ", ©, ° etc. via placeholders antes de enviar ao Google.
  - Resultado: zero "?" no documento inteiro.

Problema 3 (granularidade de blocos / paragrafos): RESOLVIDO.
  - grouper.py agrupa spans em TextBlock por (page, block_idx). Pipeline traduz por bloco.
  - _build_block_text(): une spans no mesmo y visual com espaco, linhas em y diferente com \n.
  - Resultado: espacos vazios entre spans eliminados; paragrafos fluem naturalmente.

Problema 4 (celulas de tabela / cabecalhos / rodapes): TOTALMENTE RESOLVIDO.
  Tres camadas, todas genericas:
  (a) _split_by_columns() em grouper.py (Sessao #5): separa celulas no mesmo y
      com gap > 1.5x font_size.
  (b) _get_page_vertical_lines() + _left_boundary() em writer.py (Sessao #7):
      detecta bordas verticais reais via page.get_drawings() e posiciona o
      x-inicial do texto 4pt apos a borda.
  (c) _compute_right_cap() em writer.py (Sessao #8): right-cap dinamico.
      Regra universal: nenhum bloco pode invadir x-range de outro bloco que
      compartilhe faixa vertical (>= 2pt overlap). Sem vizinho a direita ->
      margem da pagina (page_w - 30). Com vizinho -> min(neighbor.x0 - 3pt).
      Constantes: _PAGE_RIGHT_MARGIN=30, _NEIGHBOR_SAFETY=3, _MIN_VERTICAL_OVERLAP=2.
      11/11 testes unitarios passando (tests/test_writer_neighbor_cap.py).

Problema 5 (glossario tecnico): RESOLVIDO.
  - src/glossary.py: Glossary com protect/restore via __GLOSS0__, __GLOSS1__, etc.
    Matching case-insensitive, sorted by term length desc para evitar conflitos.
  - TranslationService aceita glossary opcional; protect antes de _protect(), restore depois de _restore().
  - app/glossaries.py: GlossaryStore (JSON em disco).
  - 5 endpoints REST: POST/GET/GET/PUT/DELETE /api/glossaries.
  - UI: dropdown de selecao + modal criar/remover com textarea "origem = destino".

=== MUDANCAS RECENTES IMPORTANTES EM writer.py ===

Constantes atuais de posicionamento:
  _CELL_BORDER_MARGIN  = 4.0  # pt apos a borda detectada
  _CELL_PADDING_LEFT   = 1.0  # fallback sem borda proxima
  _BORDER_SEARCH_LEFT  = 15.0 # range de busca a esquerda de bx0
  _BORDER_MIN_HEIGHT   = 8.0  # altura minima para contar como borda

Funcao _get_page_vertical_lines(page): percorre page.get_drawings(), filtra linhas
verticais e rects finos, retorna lista de x-coords de bordas.

Funcao _left_boundary(bx0, v_lines): encontra a borda mais proxima a esquerda
(dentro de _BORDER_SEARCH_LEFT), retorna border_x + _CELL_BORDER_MARGIN, ou
bx0 + _CELL_PADDING_LEFT como fallback.

Em write_translated_pdf_blocks(): por pagina, chama _get_page_vertical_lines(page).
Por bloco, chama _left_boundary(bx0, v_lines) para obter left_start do draw_rect.

=== MUDANCAS RECENTES EM translator.py ===

_DOC_CODE_RE = re.compile(r"^[A-Z0-9]{1,}([-./][A-Z0-9]{1,})+$")
Adicionado em _is_untranslatable(): codigos tecnicos (sem espacos, maiusculas+digitos
com separadores) sao retornados intactos. Ex: 109004798-001-SITE-F-0414, REV-01, A-01.

=== REGRAS DE TRABALHO ===

1. SEMPRE confirme o proximo passo comigo antes de escrever qualquer codigo.
2. Solucoes devem ser GENERICAS — nao especificas aos meus 2 PDFs de exemplo.
   O site vai receber PDFs de todo tipo. Se a solucao so funciona para um caso
   especifico, nao serve.
3. Trabalhe iterativamente: um problema de cada vez, testa, depois avanca.
4. Atualize PROGRESSO.md ao fim de cada milestone.
5. Ao fim de cada etapa, envie o comando git completo para eu rodar (com
   mensagem descritiva; use multiplos -m se precisar de multilinhas — nao use
   em-dash ou unicode no commit message, PowerShell nao suporta).
6. Paths sem acentos, ambiente Windows.
7. Arquivos Python devem ser escritos via bash python3 em UTF-8 (o Write tool
   do Cowork gera UTF-16 no mount Windows — nao usar Write para .py).
8. Claude pode renderizar paginas do PDF diretamente com PyMuPDF (nao precisa
   de screenshot manual do Miguel).
9. Ao fim de cada etapa, informe o criterio de aceitacao para eu testar.

=== PROXIMO PASSO SUGERIDO ===

ATENCAO: Os 5 problemas do briefing estao resolvidos no basico, mas PDF nativo
NAO esta 100% pronto pra producao. PDF escaneado fica para DEPOIS do site
estar rodando em producao (decisao explicita do Miguel) -- nao implementar
agora.

ORDEM CORRETA da Fase 2:

1. PRIORIDADE 1 - Suite de testes pre-producao com PDFs variados da internet.
   Baixar 8-12 PDFs diversos (relatorios publicos, artigos cientificos,
   manuais tecnicos, formularios, faturas, contratos). Rodar no pipeline com
   Google Translate real. Catalogar falhas. Esse e o passo que vai expor o
   que ainda quebra.

2. PRIORIDADE 2 - Corrigir falhas catalogadas. Cada correcao precisa de teste
   unitario travando regressao. Areas provaveis:
   - grouper.py: combinacao de celulas adjacentes em um TextBlock
   - writer.py: glifos ausentes (caracteres especiais como bullets □)
   - writer.py: insert_textbox falhando em celulas muito estreitas
   - writer.py: tabelas sem bordas visiveis

3. PRIORIDADE 3 - Recuperacao de jobs (persistencia alem do browser, historico,
   expiracao). UX importante para PDFs grandes que demoram.

Deteccao de PDF escaneado -> Fase 4, so depois do site estar rodando.
1. Deteccao de PDF escaneado: pre-analise antes de aceitar o job; se nao houver
   texto extraivel (raster/imagem), retornar erro amigavel via API.
2. Suite de testes pre-producao: baixar 8-12 PDFs variados (relatorios, artigos,
   manuais, formularios) e rodar no pipeline; coletar metricas e fixar regressoes.
3. Recuperacao de jobs: persistir status e arquivo de saida alem do tempo de
   conexao do browser; historico do usuario; expiracao apos X horas.

Arquivo do briefing completo: briefing-tradutor-pdf.md
Estado detalhado: PROGRESSO.md (o arquivo que voce acabou de ler)
```

---

## Histórico de sessões

### Sessão #10 — 2026-05-25 (Opus)

**Limitação 1 resolvida: grouper agora detecta células adjacentes via bordas verticais.**

Motivação: validação real do PDF traduzido mostrou "Distribuição: Novo Nordisk - E AFRY BR - E" atravessando bordas. Inspeção do bloco 32 do `document_pdf (1).pdf` revelou que os 3 spans (`"Distribution: "`, `"Novo Nordisk - E "`, `"AFRY BR - E "`) estavam no mesmo y com gaps de 12.5pt e 10.4pt — abaixo do threshold do grouper (1.5 × 9pt = 13.5pt). MAS havia bordas verticais detectadas em x=206.5 e x=277.4, exatamente entre os spans. O grouper antigo ignorava essas bordas e juntava tudo em um TextBlock.

Solução implementada:
- **`src/grouper.py`** — `_split_by_columns(spans, v_lines=None)`: novo parâmetro opcional. Sinal B (borda vertical) adicionado: se há borda em `(prev.x1, curr.x0)` estritamente, split mesmo com gap pequeno. `group_into_blocks(spans, v_lines_by_page=None)`: propaga v_lines por página. Compatibilidade total com chamadas sem v_lines (comportamento legacy preservado).
- **`src/pipeline.py`** — calcula `v_lines_by_page` via `_get_page_vertical_lines` (já existia em writer.py) antes de chamar o grouper. Custo: O(drawings) por página, executado uma vez por PDF.

Testes (`tests/test_grouper_borders.py`): 9 casos novos cobrindo compatibilidade legacy, borda no gap (split), borda fora do gap (não split), bordas estritamente nos limites, caso real AFRY com 3 células, paragrafo multi-linha com borda (não split), propagação por página, isolamento entre páginas. **9/9 passando.**

Validação com PDF real `document_pdf (1).pdf` (25 págs):
- Antes: 1119 TextBlocks; bloco 32 = `"Distribution: Novo Nordisk - E AFRY BR - E"` em UM bloco.
- Depois: 1136 TextBlocks (+17 casos similares detectados); bloco 32 = 3 sub-blocos separados.
- Render visual da capa: rodapé AFRY com células `"Distribuicao:"` | `"Novo Nordisk - E"` | `"AFRY BR - E"` respeitando bordas. Resto do layout intacto.

Genericidade auditada: não detecta "tabela" ou "AFRY"; usa apenas geometria de spans + bordas verticais do PDF original. Funciona em qualquer PDF nativo com layout tabular bordado, mesmo com células adjacentes coladas.

Próximo: atacar mais alguma das 4 limitações restantes (glifos ausentes, célula estreita, tabelas sem bordas, suite de testes) ou abrir P1 (suite de testes com PDFs variados).

### Sessão #9 — 2026-05-24 (Opus)

**Refinamento do right-cap: cap por borda vertical quando célula vizinha está vazia.**

Motivação: a validação real do `document_pdf (1)_pt.pdf` (Google Translate) mostrou que a Sessão #8 deixou um caso pendente — tabelas com células vazias adjacentes permitiam que o texto traduzido atravessasse bordas visíveis (`Documento Afry` invadindo 4 células vazias na capa, tabela "ANEXOS I A VI"). Causa: `_compute_right_cap` só conhecia TextBlocks vizinhos; quando a célula à direita estava vazia (sem TextBlock), o cap caía na margem da página.

Solução implementada em `src/writer.py`:
- **Nova constante:** `_BORDER_RIGHT_MARGIN = 1.0` (gap mínimo entre texto e borda vertical à direita).
- **`_compute_right_cap` estendido:** novo parâmetro opcional `v_lines: list[float] | None`. Adiciona fonte de cap "próxima borda vertical à direita" (filtra v_lines > bx1, pega a primeira que vem ordenada por `_get_page_vertical_lines`). O cap final é `min(neighbor_cap, border_cap, page_right_cap)`. Compatibilidade preservada: sem `v_lines` ou com lista vazia, comportamento equivale ao anterior.
- **`write_translated_pdf_blocks`:** passa o `v_lines` já calculado por página (uma vez) para `_compute_right_cap`. Custo adicional: O(V) por bloco, com V tipicamente < 100 → microssegundos.

Testes (`tests/test_writer_neighbor_cap.py`): 8 novos casos cobrindo legacy/None/empty v_lines, borda à direita sem vizinho, borda à esquerda ignorada, múltiplas bordas (pega mais próxima), neighbor + border (mín dos dois), border + neighbor (mín dos dois), e cenário real da tabela AFRY (bloco com 4 bordas vazias à direita). **Total: 19/19 testes passando** (11 originais + 8 novos).

Validação visual com `document_pdf (1).pdf` + mock realista (~25% expansão):
- Tabela AFRY: "Documento Afry" agora **contido na própria célula** (antes invadia 4).
- "NN Aprovador de Documentoo (Carimbo ou Assinatura)" — contido.
- "Geral Notas" — contido.
- Tabela "ANEXOS" — labels respeitam células divisórias.
- Texto corrido sem regressão.

Caso residual identificado mas **fora do escopo da Sessão #9** (escopo do `grouper.py`, Problema 3): "Distribuição: Novo Nordisk - E AFRY BR - E" continua atravessando uma borda — causa é que o `grouper` combinou em um único TextBlock duas células adjacentes muito próximas. Como é UM bloco abrangendo duas células, o right-cap (que atua entre blocos) não consegue separá-las. Documentado para possível revisita futura se causar incômodo recorrente.

Genericidade auditada: o refinamento usa apenas estruturas que o PyMuPDF já extrai (bordas via `page.get_drawings`). Funciona em qualquer PDF nativo com tabela bordada — tabelas, multi-coluna, formulários, RFQs, jornais, etc.

Próximo: Fase 2.

**Discussão final da Sessão #9 (Miguel questionou priorização):**
Miguel observou corretamente que pular para "PDF escaneado" como P1 da Fase 2 seria prematuro — PDF nativo ainda tem limitações conhecidas que não foram endereçadas. Reordenei prioridades: P1 = suite de testes com PDFs variados da internet (catalogar falhas reais), P2 = corrigir, P3 = recuperação de jobs, P4 = PDF escaneado. As 5 limitações conhecidas em PDF nativo estão documentadas na seção "Onde estamos agora" para guiar a próxima sessão.

### Sessão #8 — 2026-05-24 (Opus)

**Problema 4 totalmente resolvido com right-cap dinâmico por vizinhos.**

Motivação: Sessão #7 deixou Problema 4 parcialmente resolvido — `_split_by_columns` separava células na leitura, mas na ESCRITA o `draw_rect` ainda expandia até `page_w - 30pt`, permitindo que texto traduzido (PT ~25% mais longo) invadisse células vizinhas em tabelas. Causa identificada pela inspeção do código (não pelos sintomas reportados): faltava limite de expansão horizontal baseado em vizinhos.

Solução implementada em `src/writer.py`:
- **Novas constantes:** `_PAGE_RIGHT_MARGIN=30`, `_NEIGHBOR_SAFETY=3`, `_MIN_VERTICAL_OVERLAP=2` (todas em pt). Centralizadas para reutilização.
- **`_vertical_overlap(a, b) -> float`**: sobreposição vertical entre dois bboxes em pt; zero se disjuntos.
- **`_compute_right_cap(block_bbox, all_page_bboxes, page_w) -> float`**: regra universal "nenhum bloco invade x-range de outro bloco no mesmo y". Para cada bloco, filtra vizinhos a direita (`other.x0 > self.x1`) com sobreposição vertical ≥ 2pt; retorna `min(neighbor.x0 - safety)` limitado por margem da página. Sem vizinhos: `page_w - 30`. O próprio bloco é auto-excluído pelo filtro (`bx0 <= bx1`).
- **Integração em `write_translated_pdf_blocks`**: pré-calcula lista de bboxes da página uma única vez por página (O(N²) total em vez de O(N³)); cada bloco usa `_compute_right_cap` para definir `bx1_safe`. Política preservada: nunca reduz abaixo do `bx1` original (não regride layouts onde bloco já era largo).
- Substituição cosmética: `30.0` hardcoded no `write_translated_pdf` legado trocado por `_PAGE_RIGHT_MARGIN`.

Testes (`tests/test_writer_neighbor_cap.py`): 11 casos cobrindo bloco isolado, vizinho no mesmo y, vizinho em y diferente, vizinho à esquerda, múltiplos vizinhos, sobreposição parcial, sobreposição negligível, cap pela margem da página, e linha de tabela de 3 colunas. **11/11 passando.**

Validação visual:
- `document_pdf (1).pdf` (25 págs) com mock agressivo +80% (extremo): capa renderizada — células `Approv.` e `Emission Purpose` da tabela de revisões respeitam vizinhos; tabela AFRY de baixo respeita estrutura. Casos onde texto não cabe nem em 6pt: trade-off correto (truncar vs invadir vizinho).
- `document_pdf.pdf` (42 págs) com mock realista ~25%: páginas 5 e 15 visualmente íntegras — sem invasão entre células, texto corrido (bullets, parágrafos) fluindo natural, cabeçalho de tabela do topo limpo.

Genericidade auditada: não há detecção de "tabela", "rodapé" ou conteúdo específico. A regra opera apenas sobre bboxes e sobreposição vertical — funciona em qualquer PDF nativo (tabelas, multi-coluna, formulários, RFQs, jornais, etc.).

Custo computacional: O(N²) por página para o cálculo de right-caps. N tipicamente < 200 mesmo em PDFs densos → < 1ms por página. Escala linear com número de páginas.

Validação com PDF real (Google Translate, `document_pdf (1)_pt.pdf`): layout ~95% íntegro. Texto corrido, listas, tabelas com colunas preenchidas, cabeçalhos de tabela, códigos de documento (`MOC4-08-9600-RFQ-004-AFRY`) — tudo limpo. Tradução técnica fluida ("Solicitação de cotação", "PROPONENTE", "CONTRATANTE", "Designer Líder do Projeto Executivo").

**Issue residual identificado mas NÃO implementado** (créditos da sessão acabando, decisão do Miguel de adiar): tabelas com células vazias adjacentes (caso AFRY na capa, tabela "ANEXOS I A VI") permitem que o texto traduzido atravesse bordas verticais visíveis, porque o `_compute_right_cap` só conhece TextBlocks como vizinhos. Documentado na seção "Onde estamos agora" e no prompt de retomada como **PRIORIDADE 1 da próxima sessão**.

Próximo: implementar extensão do right-cap com bordas verticais; depois Fase 2 (detecção de PDF escaneado, suite de testes pré-produção, recuperação de jobs).

### Sessão #7 — 2026-05-24

**Correções genéricas de tabela e documento (não-específicas aos PDFs de exemplo):**

- **`src/grouper.py`** — `_COLUMN_GAP_RATIO`: 2.0 → 1.5. Causa raiz do "Docu|mentos": gap real entre colunas (20.2pt) ficava abaixo do threshold antigo (22pt) e não separava. Com 1.5, threshold = 16.5pt → separa corretamente. Genérico: funciona para qualquer tabela onde o gap de coluna > 1.5× o tamanho da fonte.

- **`src/writer.py`** — Substituído padding fixo (`_CELL_PADDING_LEFT = 2pt`) por detecção real de bordas via `page.get_drawings()`. Novas funções `_get_page_vertical_lines()` e `_left_boundary()`: detectam linhas/rects verticais finos (bordas de tabela) e posicionam o texto 4pt após a borda detectada. Fallback de 1pt quando não há borda próxima. Genérico: funciona com qualquer PDF que represente bordas de tabela como linhas ou rects finos.

- **`src/translator.py`** — `_DOC_CODE_RE`: novo regex para detectar códigos técnicos de documento (ex: `109004798-001-SITE-F-0414`, `REV-01`, `A-01`) como intraduzíveis. Critério: sem espaços, maiúsculas/dígitos com separadores (-, ., /). Genérico: preserva qualquer código técnico nesse formato sem intervenção do usuário.

- Todos os três testes unitários passaram: column split, border detection, doc code protection.

### Sessão #6 — 2026-05-24
- Fix cosmético em `writer.py`: adicionada constante `_CELL_PADDING_LEFT = 2.0` e aplicada ao `draw_rect` de `write_translated_pdf_blocks()` (`bx0 + _CELL_PADDING_LEFT`). Corrige artefato visual de "texto cortado" pela linha divisória de células de tabela.
- Problema 3 oficialmente encerrado.
- **Problema 5 — Glossário técnico:** novo módulo `src/glossary.py` (classe `Glossary` com protect/restore via `__GLOSS0__`). `TranslationService` aceita `glossary` opcional. `pipeline.py` aceita `glossary_path`. `app/glossaries.py` com `GlossaryStore` (JSON em disco). 5 endpoints REST em `app/main.py`. UI atualizada: dropdown de seleção + modal criar/remover com textarea `origem = destino`.
- Fase 1 dos 5 problemas: Problemas 1, 2, 3 e 5 resolvidos. Problema 4 (cabeçalhos/rodapés) a definir.

### Sessão #5 — 2026-05-23/24
- Problema 1 (expansão de texto): extractor.py recebe line_x1 e page_w por span; writer.py usa espaço real da linha como draw_rect, capeia na margem (page_w - 30pt).
- Redução de fonte: 3 passos rápidos (90/80/70%) antes da descida fina; mínimo 6pt (era 4pt).
- Resultado: 229 overflows → 0. Layout validado visualmente.
- Nota técnica: Write tool gera UTF-16 no mount Windows — arquivos precisam ser reescritos pelo bash em UTF-8 quando editados pelo sandbox.
- Próximo: Problema 3 (agrupamento de parágrafos).

### Sessão #3 — 2026-05-23
- Problema 2 (fontes): substituídas fontes base14 (Latin-1) por NotoSans via `pymupdf-fonts`.
- `src/writer.py` refatorado: detecta bold/italic e usa variante correta (notos/notosbo/notosit/notosbi). Fallback gracioso para base14 se o pacote não estiver instalado.
- `requirements.txt` atualizado com `pymupdf-fonts>=1.0.5`.
- Fix adicional em `src/translator.py`: protect/restore de `–`, `•`, `'`, `"`, `©`, `°` etc. — Google Translate malhava esses chars para `?`. Spans com apenas símbolos/números pulam a tradução. NBSP normalizado para espaço normal.
- **Validado com Google Translate real (PDF 25 págs):** zero "?" no documento inteiro. Bullets e en-dashes renderizando corretamente.
- Critério de aceitação do Problema 2: ✅ ATINGIDO.
- Próximo: Problema 1 (expansão de texto) ou Problema 3 (agrupamento de parágrafos).

### Sessão #2 — 2026-05-23
- Retomada do projeto. Confirmei todos os arquivos em disco.
- Ajustes preventivos: removido import `StaticFiles` não usado; adicionado `request_delay=0.05s` no pipeline.
- Miguel rodou localmente: `document_pdf.pdf` (42 págs) traduzido com Google Translate real.
- **Fase 0 validada:** layout, logos, tabelas preservados. Caracteres "?" em alguns spans (Problema 2 de fontes).
- Decisões de produto coletadas: modelo de créditos, recuperação de jobs, pré-análise de PDF escaneado.
- Próximo: Problema 2 — suporte Unicode nas fontes (eliminar "?").

### Sessão #1 — 2026-05-23
- Recebi o briefing completo (`briefing-tradutor-pdf.md`).
- Decisões: tradutor gratuito (Google), piloto fullstack, tradução crua na Fase 0.
- Inspecionei os 2 PDFs reais: `document_pdf.pdf` (42 págs) e `document_pdf (1).pdf` (25 págs) — ambos PDFs nativos do Word, totalmente compatíveis com a abordagem in-place.
- Criei estrutura de pastas, `requirements.txt`, `.env.example`, `.gitignore`, `pyproject.toml`.
- Implementei pipeline core: `extractor.py`, `translator.py`, `writer.py`, `pipeline.py`, `cli.py`.
- Implementei backend FastAPI completo: `main.py`, `jobs.py`, `auth.py`, `billing.py`, `quotas.py`.
- Implementei frontend `index.html` (Tailwind CDN, drag-and-drop, progress, download).
- Validei pipeline end-to-end com translator MOCK no sandbox (sandbox bloqueia rede externa para Google). Resultado visual: layout, logos, tabelas e branding 100% preservados; texto substituído em 1512 spans / 25 páginas em ~4s.
- Identifiquei limitação conhecida: estratégia de "pintar branco + escrever por cima" deixa camada de texto antiga embaixo — texto fica visualmente correto mas extractors textuais leem duplicado. Solução para Fase 1: trocar `draw_rect` por `add_redact_annot` + `apply_redactions`.
- Criei `setup_git.ps1` apontando para o repo `miguelribeirocodes/smart-pdf-translator`.
- Criei `README.md` final.
- **Pendente do Miguel:** rodar `setup_git.ps1` para subir tudo no GitHub e depois `uvicorn app.main:app --reload` para testar com Google Translate real.

### Sessão #5 — 2026-05-23
- Problema 1 aceito por Miguel: critério cumprido (zero overflows fora da página).
- Nota de produto: criar suite de testes pré-produção — baixar PDFs variados da internet e rodar no app para validar edge cases reais antes do lançamento.
- Fix crítico de tabelas: novo _split_by_columns() no grouper.py — detecta células de tabela (spans no mesmo y com gap > 2x font_size) e as divide em sub-blocos independentes. Parágrafos não afetados. Corrige o zoado da tabela de capa reportado pelo Miguel.
- Problema 3 CONCLUÍDO: novo src/grouper.py (TextBlock, group_into_blocks); pipeline.py usa blocos; writer.py escreve por bloco.
- Fix crítico no grouper: spans no mesmo y visual (campos tabulados, ex: "1." + "INTRODUCTION..." na TOC) são unidos com espaço em vez de \n. Linhas em y diferente usam \n (listas, títulos multi-linha).
- Resultado: TOC com entradas completas, parágrafos fluindo naturalmente, lista de Annex titles com quebras corretas.
- Próximo: Problema 4 (cabeçalhos/rodapés/tabelas). Sonnet.

<!-- Próxima sessão: adicionar entrada aqui antes de fechar -->
