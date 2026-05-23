# Tradutor PDF — preservação de layout

Ferramenta em Python que traduz PDFs **alterando o texto interno in-place**, preservando fontes, cores, imagens e estrutura visual do documento original. Funciona em PDFs nativos (gerados por Word, InDesign, LaTeX), não em PDFs escaneados.

> Estado atual: **Fase 0 — piloto fullstack com tradução crua.**
> Para o plano completo, ver [`briefing-tradutor-pdf.md`](briefing-tradutor-pdf.md).
> Para o estado vivo do projeto, ver [`PROGRESSO.md`](PROGRESSO.md).

## O que já funciona

- Backend FastAPI com endpoints REST (`/api/translate`, `/api/jobs/{id}`, `/api/jobs/{id}/download`).
- Frontend HTML + Tailwind (CDN) com drag-and-drop, seletor de idiomas e barra de progresso.
- Pipeline core: extração via PyMuPDF → tradução via Google (gratuito, fallback MyMemory) → reescrita in-place.
- Suporte a 10 idiomas (en, pt, es, fr, de, it, ja, zh-CN, ru, nl).
- CLI standalone (`cli.py`) para uso fora do web app.
- Hooks de auth, billing e quotas como placeholders prontos para futuro.

## Limitações conhecidas (atacar na Fase 1)

São os **5 problemas técnicos** do briefing, propositadamente adiados:

1. **Expansão de texto** — português é ~20% mais longo. Hoje o writer reduz a fonte até caber; pode cortar ou ficar pequeno.
2. **Fontes sem charset latino** — usamos Helvetica sempre. A fonte original não é preservada.
3. **Granularidade de blocos** — traduzimos span por span (PyMuPDF). Tradução por parágrafo logical seria melhor.
4. **Cabeçalhos/rodapés/tabelas** — sem tratamento especial. Tabelas podem ter células estouradas.
5. **Glossário técnico** — sem proteção de termos. Códigos de projeto e siglas podem ser traduzidos indevidamente.

Detalhe adicional: a estratégia de "pintar branco e escrever por cima" deixa a camada de texto antiga embaixo. Visualmente o PDF mostra só o traduzido, mas extractors textuais (não visuais) verão o texto duplicado. A solução é trocar `draw_rect` por `add_redact_annot` + `apply_redactions` na Fase 1.

## Como rodar

### 1. Pré-requisitos

- Python 3.10+
- Conexão à internet (Google Translate gratuito via `deep-translator`)

### 2. Setup

```bash
git clone https://github.com/miguelribeirocodes/smart-pdf-translator.git
cd smart-pdf-translator

python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/Mac:
# source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Subir o servidor

```bash
uvicorn app.main:app --reload --port 8000
```

Abra http://localhost:8000 no navegador. Arraste um PDF, escolha os idiomas, clique em "Traduzir".

### 4. Usar via CLI (alternativa)

```bash
python cli.py document_pdf.pdf --from en --to pt -o output.pdf
```

## Estrutura

```
smart-pdf-translator/
├── briefing-tradutor-pdf.md      Briefing original (plano de referência)
├── PROGRESSO.md                  Save state vivo, atualizado a cada sessão
├── README.md                     Este arquivo
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── setup_git.ps1                 Script de bootstrap do git
├── cli.py                        Entry point CLI
│
├── src/                          Pipeline core (puro, sem dependência web)
│   ├── extractor.py              Lê spans com PyMuPDF
│   ├── translator.py             Wrapper de provedores (Google, MyMemory)
│   ├── writer.py                 Reescreve PDF in-place
│   └── pipeline.py               Orquestrador
│
├── app/                          Aplicação web FastAPI
│   ├── main.py                   App + rotas
│   ├── jobs.py                   Store de jobs (in-memory)
│   ├── auth.py                   Placeholder de autenticação
│   ├── billing.py                Placeholder de cobrança
│   ├── quotas.py                 Placeholder de cotas
│   ├── templates/index.html      Frontend
│   └── storage/                  Uploads e outputs (gitignored)
│
├── tests/
│   └── test_extractor.py
└── examples/
    ├── input/
    └── output/
```

## Próximos passos

Ver `PROGRESSO.md` seção "Checklist de implementação". Em ordem sugerida:

1. Trocar a estratégia de pintura branca por redaction real (sem texto duplicado embaixo).
2. Atacar Problema 1 (expansão de texto) com lógica de quebra inteligente.
3. Atacar Problema 3 (reagrupar spans em parágrafos lógicos) — melhora a qualidade da tradução.
4. Adicionar glossário JSON por projeto (Problema 5).
5. Persistir jobs em SQLite/Postgres em vez de dict em memória.
6. Adicionar Claude/DeepL como providers premium.

## Licença

A definir.
