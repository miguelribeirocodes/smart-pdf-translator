# Briefing: Ferramenta de Tradução de PDF com Preservação de Layout

> Este documento é o briefing completo para desenvolver o projeto. Cole-o (ou o "Prompt Inicial" no final) em uma nova sessão do Cowork para começar.

---

## 1. Contexto e motivação

Sou Miguel, Automation Specialist com forte background em Python, manipulação de documentos (ReportLab, PyMuPDF, openpyxl) e automação de processos. No meu trabalho lido frequentemente com PDFs técnicos corporativos (RFQs, especificações de engenharia, documentos da Novo Nordisk/AFRY com branding preservado) e já recriei vários desses documentos em português usando ReportLab — recriando o PDF do zero.

**O problema com a abordagem atual de recriação:** é trabalhosa, frágil a mudanças de layout, exige replicar manualmente fontes, cores, branding, tabelas, e não escala.

**A ideia do projeto:** uma ferramenta que **altera o texto interno do PDF original** in-place, traduzindo blocos de texto enquanto preserva o layout, fontes, cores e elementos gráficos do documento original.

**Por que isso é viável:** PDFs gerados nativamente por software (Word, InDesign, LaTeX) armazenam texto como objetos estruturados com coordenadas (x, y), fonte, tamanho e cor. É possível ler esses blocos, traduzi-los e reescrevê-los no mesmo local.

---

## 2. Mercado e diferencial

Já existem ferramentas como DocTranslator, DeepL Pro (tradução de documentos), Google Translate (upload), Adobe Acrobat com plugin. Todas falham em um ou mais destes pontos:

- Quebram o layout em documentos complexos
- Não suportam glossário técnico customizado (termos que NÃO devem ser traduzidos: códigos de projeto, siglas, nomes próprios)
- São caras para o mercado brasileiro (pagam em USD/EUR)
- Não preservam branding corporativo
- Tratam mal expansão de texto (português é ~20% mais longo que inglês)

**Diferencial pretendido:** ferramenta brasileira, paga em real, focada em **documentos técnicos** (engenharia, jurídico, médico, RFQs, manuais) com **glossário customizável** e **preservação fiel de layout**.

---

## 3. Os 5 problemas técnicos centrais

Esses são os pontos onde a maioria das ferramentas existentes falha e onde está a oportunidade de diferenciação. **A solução precisa atacar cada um deles.**

### Problema 1: Expansão de texto
Português é 15-30% mais longo que inglês. Texto que cabia em uma linha pode estourar a caixa após tradução.
- **Solução:** ajuste automático de tamanho da fonte, quebra inteligente de linha, ou expansão da caixa quando houver espaço em branco ao redor.

### Problema 2: Fontes embutidas sem suporte a charset latino
Algumas fontes do PDF original podem não suportar caracteres acentuados (ç, ã, é). Tentar escrever "manutenção" nessas fontes produz quadrados em branco.
- **Solução:** detectar fonte, verificar suporte ao charset Latin-1/UTF-8, substituir por fonte equivalente quando não suportar (manter família visualmente similar).

### Problema 3: Granularidade de blocos
PDFs nem sempre guardam "parágrafo" como unidade. Podem guardar palavra-por-palavra ou linha-por-linha. Traduzir nessa granularidade dá tradução ruim.
- **Solução:** reagrupar palavras/linhas em parágrafos lógicos antes de enviar para tradução, e depois redistribuir o texto traduzido nas linhas originais respeitando o layout.

### Problema 4: Elementos repetitivos e estruturados
Cabeçalhos, rodapés, números de página, tabelas. Cada um tem comportamento próprio.
- **Solução:** detecção heurística de cabeçalhos/rodapés (texto que se repete em múltiplas páginas), tratamento especial para tabelas (preservar estrutura de células), evitar tradução de números de página e códigos.

### Problema 5: Glossário técnico
Documentos técnicos têm termos que NÃO devem ser traduzidos (códigos de projeto como "MOC4-08-9600-RFQ-004-AFRY", siglas, nomes próprios, nomes de produtos).
- **Solução:** sistema de glossário customizado por documento ou cliente, com regras de "não traduzir" e "traduzir como X".

---

## 4. Stack técnica sugerida

### Manipulação de PDF
- **PyMuPDF** (instalado via `pip install pymupdf`, importado como `import pymupdf` ou `import fitz` para compatibilidade retroativa) — biblioteca principal. Lê blocos de texto com coordenadas, fonte, tamanho, cor. Permite apagar e reescrever texto in-place.
- Alternativa/complemento: `pdfplumber` para extração de tabelas, se PyMuPDF não for suficiente.

### Tradução
Três opções, em ordem de qualidade vs custo:
1. **DeepL API** — melhor qualidade para idiomas europeus. Custo: ~€5,49/mês + €20 por milhão de caracteres no plano Pro.
2. **API da Anthropic (Claude) ou OpenAI** — excelente para contexto técnico, permite prompt com glossário e instruções. Mais caro por token mas qualidade superior para jargão.
3. **Google Cloud Translation API** — barata, qualidade razoável, boa para volume.

Recomendação inicial: **Claude/GPT para qualidade técnica**, com possibilidade de DeepL como fallback ou opção econômica.

### Backend (para versão SaaS futura)
- **FastAPI** — Python, async, fácil de integrar com o pipeline.
- **Celery + Redis** para processamento assíncrono de PDFs longos.
- **PostgreSQL** para usuários, glossários, histórico de traduções.

### Frontend (versão SaaS futura)
- **Next.js** ou simplesmente HTML + Tailwind para começar.
- Upload de PDF, seleção de idiomas, glossário, download do resultado.

### Pagamento (versão SaaS futura)
- **Stripe** ou **Mercado Pago** (preferível para mercado BR).

---

## 5. Plano de desenvolvimento em fases

### Fase 0: Protótipo mínimo (1 fim de semana)
Objetivo: validar a abordagem técnica.

- [ ] Setup do projeto: venv, dependências, estrutura de pastas.
- [ ] Script que lê um PDF nativo simples (1-3 páginas) e extrai blocos de texto com coordenadas, fonte, tamanho, cor usando PyMuPDF.
- [ ] Integração com API de tradução (Claude ou DeepL).
- [ ] Reescrever texto traduzido nas mesmas coordenadas.
- [ ] Salvar PDF resultante.
- [ ] Testar com 3-5 PDFs reais de complexidade variada.

**Critério de sucesso:** PDF traduzido sai com layout reconhecível e texto legível, mesmo que com falhas pontuais.

### Fase 1: MVP funcional (2-4 semanas)
Objetivo: ferramenta que resolve 80% dos casos de PDFs técnicos nativos.

- [ ] Tratar expansão de texto: ajuste de fonte ou quebra inteligente.
- [ ] Detectar e substituir fontes sem suporte a charset latino.
- [ ] Reagrupar texto em parágrafos lógicos antes de traduzir.
- [ ] Implementar glossário básico (arquivo JSON ou YAML por projeto).
- [ ] CLI simples: `python translate_pdf.py input.pdf --to pt --glossary glossary.json`.
- [ ] Logs detalhados (quais blocos foram traduzidos, quais foram pulados, erros).

**Critério de sucesso:** rodar em um RFQ real (tipo Novo Nordisk/AFRY) e obter resultado utilizável com mínima edição manual.

### Fase 2: Robustez e edge cases (4-8 semanas)
- [ ] Detecção heurística de cabeçalhos/rodapés.
- [ ] Tratamento especial para tabelas.
- [ ] Detecção de PDFs escaneados (raster) e mensagem clara ao usuário (ou OCR opcional via Tesseract).
- [ ] Suporte a múltiplos idiomas (en↔pt, es↔pt, pt↔en, etc.).
- [ ] Comparação visual lado-a-lado (gerar imagem de antes/depois de cada página para inspeção).

### Fase 3: Produto (modelo a decidir)
Três caminhos possíveis (decidir conforme feedback de uso real):

**Caminho A — Web app self-service**
Cliente faz upload, paga por página ou por crédito, baixa resultado. Stack: FastAPI + frontend simples + Stripe/Mercado Pago. Cobra R$ 0,50-2,00 por página ou pacote mensal R$ 50-200.

**Caminho B — SaaS B2B nichado**
Foco em escritórios de engenharia, jurídicos, consultorias internacionais. Mensalidade R$ 300-1.500/mês com volume incluído + glossário customizado por cliente. Menos clientes, ticket muito maior.

**Caminho C — Ferramenta + serviço híbrido**
Usar a ferramenta internamente para acelerar trabalho manual de tradução técnica oferecido como serviço. Cobrar como tradutor profissional (R$ 0,15-0,40 por palavra), entregar em fração do tempo. Margem altíssima, sem precisar polir o produto até nível SaaS.

---

## 6. Estrutura de pastas sugerida

```
tradutor-pdf/
├── README.md
├── requirements.txt
├── .env.example          # ANTHROPIC_API_KEY, DEEPL_API_KEY, etc.
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── extractor.py      # Extrai blocos de texto do PDF
│   ├── translator.py     # Wrapper para APIs de tradução
│   ├── glossary.py       # Carrega e aplica glossário
│   ├── writer.py         # Reescreve texto no PDF
│   ├── fonts.py          # Detecção e substituição de fontes
│   ├── layout.py         # Lógica de ajuste de layout (fonte, quebra)
│   └── pipeline.py       # Orquestrador principal
├── tests/
│   ├── fixtures/         # PDFs de teste
│   └── test_*.py
├── examples/
│   ├── input/
│   └── output/
└── cli.py                # Entry point CLI
```

**Importante sobre caminhos:** evitar acentos e espaços em nomes de pasta/arquivo (problema conhecido no setup do Claude Code em paths com acentos).

---

## 7. Decisões em aberto para discutir no Cowork

- [ ] DeepL vs Claude/GPT como tradutor principal? (Sugestão: Claude para qualidade técnica, com glossário no prompt do sistema.)
- [ ] Como detectar parágrafos lógicos a partir de blocos de baixo nível do PyMuPDF? (Heurística por proximidade vertical, indentação, espaçamento.)
- [ ] Estratégia para substituição de fonte: manter família visualmente similar (ex: Helvetica → Arial) ou padronizar tudo para uma fonte segura (DejaVu Sans)?
- [ ] Formato do glossário: JSON simples, YAML, ou interface web?
- [ ] Modelo de monetização: por página, por documento, por assinatura?
- [ ] Open source (build in public) ou fechado?

---

## 8. Prompt inicial para colar no Cowork

> Copie a partir daqui ao iniciar uma nova sessão do Cowork.

```
Estou desenvolvendo uma ferramenta em Python para traduzir PDFs preservando o layout
original. A ideia é ler o texto interno do PDF, traduzir via API e reescrever as
strings traduzidas nas mesmas coordenadas, mantendo fontes, cores e estrutura visual.

Contexto:
- Sou Automation Specialist com forte experiência em Python e manipulação de documentos.
- Já uso ReportLab para recriar PDFs traduzidos do zero, mas é trabalhoso. Quero
  evoluir para alterar o texto in-place.
- Foco em documentos técnicos corporativos (RFQs, especificações de engenharia,
  manuais) — não literatura.
- Stack: Python + PyMuPDF (pip install pymupdf) + API de tradução (Claude ou DeepL).

Os 5 problemas técnicos centrais que o projeto precisa resolver:
1. Expansão de texto (PT é ~20% mais longo que EN) — ajuste de fonte ou quebra.
2. Fontes sem suporte a charset latino — detecção e substituição.
3. Granularidade de blocos — reagrupar em parágrafos antes de traduzir.
4. Cabeçalhos, rodapés, tabelas — tratamento especial.
5. Glossário técnico — termos que não devem ser traduzidos.

Quero começar pela Fase 0: protótipo mínimo de fim de semana que leia um PDF
nativo, extraia blocos de texto com coordenadas e atributos via PyMuPDF, traduza
via API e reescreva no mesmo lugar. Sem se preocupar ainda com edge cases.

Antes de escrever código, me ajude a:
1. Validar a arquitetura básica do protótipo.
2. Definir a estrutura de dados intermediária (como representar um bloco de texto
   extraído entre a leitura e a escrita).
3. Escrever o primeiro script funcional do extractor.py.

Trabalhe iterativamente: passo a passo, com testes em PDFs reais a cada etapa.
Caminhos sem acentos nem espaços (problema conhecido em setup com paths com
acentos no Windows).
```

---

## 9. Referências úteis

- PyMuPDF docs: https://pymupdf.readthedocs.io/
- PyMuPDF GitHub: https://github.com/pymupdf/PyMuPDF
- DeepL API: https://www.deepl.com/pro-api
- Anthropic API docs: https://docs.claude.com/
- pdfplumber (alternativa/complemento): https://github.com/jsvine/pdfplumber

---

## 10. Observações honestas sobre riscos

- **IA generativa está comendo esse mercado.** Em 2026, modelos como Claude e GPT-4o já leem PDFs e devolvem versões traduzidas com layout razoável. O diferencial precisa estar nos pontos onde LLM puro falha: **glossário técnico estrito, preservação fiel de fontes/cores corporativas, processamento em batch e custo previsível**.
- **Os primeiros 70% do produto são fáceis; os últimos 30% são meses de trabalho.** PDFs malformados, fontes esquisitas, tabelas complexas são o inferno do edge case.
- **Validar com usuários reais cedo.** Não desenvolver 6 meses para depois descobrir que ninguém paga. A colega que pede tradução de graça NÃO é o cliente — é referência de problema, não de mercado.
- **O Caminho C (ferramenta + serviço) é o mais seguro para começar.** Mesmo que o produto nunca vire SaaS, a ferramenta acelera trabalho que você cobra como serviço.

---

**Próximo passo recomendado:** abrir o Cowork, criar a pasta do projeto (sem acentos), colar o "Prompt inicial" da seção 8 e começar pela Fase 0.
