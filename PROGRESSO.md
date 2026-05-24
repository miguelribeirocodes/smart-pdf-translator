# PROGRESSO — Tradutor PDF

> **Save state vivo do projeto.** Atualizado a cada sessão de trabalho.
> Para a visão completa do plano, ver [`briefing-tradutor-pdf.md`](briefing-tradutor-pdf.md).
> Para retomar em outra máquina, ver a seção [**"Prompt de retomada"**](#prompt-de-retomada) no final.

---

## Onde estamos agora

**Fase atual:** Fase 1 — Qualidade de tradução e robustez.

**Última sessão:** 2026-05-24 (Sessão #6/7). Correções genéricas de tabela e códigos de documento aplicadas.

**Próximo bloco de trabalho:** Problema 4 pendente (rodapés/cabeçalhos de tabela persistentes em todas as páginas — texto sobreposto). Avaliar solução genérica vs. backlog Fase 2. **Usar Opus para esta sessão em diante.**

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
| Problema 4 — cabeçalhos/rodapés/tabelas | **Opus** ← ATUAL | Detectar blocos repetitivos entre páginas; heurística mais complexa |
| Problema 5 — glossário técnico | ~~Sonnet~~ ✅ concluído | — |
| Fase 2 — suite de testes, detecção de PDF escaneado | **Opus** | Decisões de estratégia de testes e edge cases |
| Arquitetura de produto (Fase 3 — decisão A/B/C) | **Opus** | Decisão estratégica de alto impacto |
| Auth + Billing real | **Sonnet** | Implementação padrão |

**Resumo:** Migrado para Opus a partir da Sessão #8. Problema 4 (rodapés/cabeçalhos) envolve heurística de detecção de blocos repetitivos — tarefa adequada para Opus. Fase 3 em diante também Opus para decisões arquiteturais.

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
- [x] **Problema 4: Tabelas (células multi-coluna)** — ✅ resolvido (Sessão #5). `grouper.py`: novo `_split_by_columns()` detecta spans na mesma y-visual com grandes gaps horizontais (> 2× font_size) e os divide em sub-blocos individuais por célula. Parágrafos multi-linha não são afetados. Blocos: 680 → 1049 (inclui 369 sub-blocos de células de tabela). Cabeçalhos/rodapés persistentes a tratar em Problema 4 real.
- [x] **Problema 5: Glossário técnico** — ✅ resolvido (Sessão #6). Novo módulo `src/glossary.py` com classe `Glossary`: protect/restore de termos via placeholders `__GLOSS0__` antes de enviar ao provedor. `TranslationService` recebe `glossary` opcional. `pipeline.py` aceita `glossary_path` opcional. `app/glossaries.py`: `GlossaryStore` com persistência em JSON (`app/storage/glossaries/`). 5 endpoints REST (`POST/GET/PUT/DELETE /api/glossaries`). UI: dropdown para selecionar glossário + modal para criar/remover glossários com textarea `origem = destino`.

#### Fase 2 — robustez
- [ ] **Suite de testes pré-produção** — baixar ~10 PDFs variados (relatórios, artigos, manuais, formulários) da internet e rodar no app antes de ir à produção. Validar edge cases reais: multi-coluna, tabelas complexas, fontes exóticas, PDFs grandes.
- [ ] **Detecção de PDF escaneado** — pré-análise antes de traduzir: bloquear na API com mensagem clara se PDF for raster/imagem (sem texto extraível). OCR Tesseract como opção futura.
- [ ] **Recuperação de jobs** — job persiste mesmo se usuário fechar o browser; histórico de jobs acessível; arquivo fica disponível por X horas após conclusão.
- [ ] Comparação visual lado-a-lado (antes/depois por página)
- [ ] Suporte a múltiplos pares de idioma testados

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

Problema 4 (celulas de tabela): PARCIALMENTE RESOLVIDO. Pendencias em aberto.
  RESOLVIDO:
  - _split_by_columns() em grouper.py: detecta celulas no mesmo y com gap > 1.5x font_size
    e as separa em sub-blocos. _COLUMN_GAP_RATIO = 1.5 (era 2.0; gap critico era 20.2pt,
    threshold antigo era 22pt — nao separava; novo threshold = 16.5pt — separa).
  - _get_page_vertical_lines() + _left_boundary() em writer.py: detecta bordas de tabela via
    page.get_drawings() (linhas verticais finas |dx|<2pt, altura>=8pt; rects finos width<2pt).
    Posiciona texto 4pt apos a borda detectada (fallback: 1pt).
  PENDENTE — problema visual que "melhorou um pouco" mas nao esta 100%:
  - Rodapes persistentes em tabelas do PDF de 42 paginas: o texto "Afry Document Number:"
    e o numero de documento aparecem como rodape em todas as paginas. Quando estao na mesma
    linha da tabela de rodape, os spans podem se misturar causando texto sobreposto ou
    cortado na borda da celula.
  - Causa raiz suspeitada: elementos que se repetem na mesma posicao em todas as paginas
    (cabecalhos/rodapes de tabela nao sao separados como estrutura — sao apenas spans no
    texto principal). Deteccao de blocos repetitivos entre paginas seria a solucao ideal
    (Fase 2 scope), mas pode haver ajuste pontual possivel antes disso.

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

Problema 4 pendente (rodapes/cabecalhos de tabela que se repetem em todas as
paginas e causam texto sobreposto ou cortado). Avaliar:
a) Se ha solucao generica suficientemente simples para implementar agora.
b) Ou se deve ir para o backlog da Fase 2 (deteccao de blocos repetitivos).

Depois: Fase 2 — suite de testes pre-producao com PDFs variados, deteccao de
PDF escaneado, recuperacao de jobs.

Arquivo do briefing completo: briefing-tradutor-pdf.md
Estado detalhado: PROGRESSO.md (o arquivo que voce acabou de ler)
```

---

## Histórico de sessões

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
