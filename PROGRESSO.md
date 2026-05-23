# PROGRESSO — Tradutor PDF

> **Save state vivo do projeto.** Atualizado a cada sessão de trabalho.
> Para a visão completa do plano, ver [`briefing-tradutor-pdf.md`](briefing-tradutor-pdf.md).
> Para retomar em outra máquina, ver a seção [**"Prompt de retomada"**](#prompt-de-retomada) no final.

---

## Onde estamos agora

**Fase atual:** Fase 1 — Qualidade de tradução e robustez.

**Última sessão:** 2026-05-23 (Sessão #2). Fase 0 validada com PDF real de 42 páginas (Google Translate). Resultado: layout, logos e tabelas 100% preservados. Problema visível: caracteres especiais renderizados como "?" (Problema 2 — fontes). Observações de produto coletadas do Miguel (ver seção de decisões).

**Próximo bloco de trabalho:** Problema 2 (fontes) — eliminar os "?" substituindo fontes originais por fontes embutidas com suporte Unicode completo.

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
- [ ] **Problema 2: Fontes sem charset Unicode** — ⬅️ **PRÓXIMO** — eliminar "?" embutindo fonte com suporte completo (ex: NotoSans via fonttools/reportlab ou registrar TTF no PyMuPDF)
- [ ] **Problema 1: Expansão de texto** — ajuste de fonte mais inteligente, quebra de linha
- [ ] **Problema 3: Granularidade de blocos** — reagrupar spans em parágrafos lógicos antes de traduzir
- [ ] **Problema 4: Cabeçalhos/rodapés/tabelas** — detecção heurística e tratamento especial
- [ ] **Problema 5: Glossário técnico** — sistema de termos protegidos (JSON/YAML por projeto)

#### Fase 2 — robustez
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

> Cole o bloco abaixo numa nova sessão do Cowork para retomar exatamente de onde paramos.

```
Estou retomando o projeto Tradutor PDF (preservacao de layout).

Contexto rapido:
- Sou Miguel, Automation Specialist. Quero uma ferramenta que traduz PDFs
  preservando layout, fontes e branding.
- O briefing completo esta em briefing-tradutor-pdf.md.
- O estado atual e o que ja foi feito esta em PROGRESSO.md (LEIA esse arquivo
  primeiro, ele tem a verdade do projeto).

Decisoes ja tomadas que estao no PROGRESSO.md:
- Tradutor gratuito (Google via deep-translator) na Fase 0; trocar depois.
- Piloto fullstack desde o inicio (FastAPI + HTML/Tailwind), nao CLI mininal.
- Tradutcao crua na Fase 0; os 5 problemas tecnicos do briefing ficam para
  Fase 1+.
- Multi-idioma e hooks de auth/billing arquitetados desde ja, mas em stub.

Antes de seguir, por favor:
1. Leia PROGRESSO.md inteiro.
2. Cheque o checklist e me diga em que item paramos.
3. Confirme comigo qual e o proximo passo antes de codificar.
4. Trabalhe iterativamente, atualize PROGRESSO.md ao fim de cada milestone, e
   sugira commits descritivos para eu rodar.

Paths sem acentos, ambiente Windows.
```

---

## Histórico de sessões

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

<!-- Próxima sessão: adicionar entrada aqui antes de fechar -->
