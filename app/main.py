"""
Backend FastAPI do Tradutor PDF.

Endpoints (Fase 0):
  POST /api/translate         - upload de PDF + idiomas, retorna job_id
  GET  /api/jobs/{id}         - status atual do job
  GET  /api/jobs/{id}/download - baixa o PDF traduzido (quando pronto)
  GET  /api/languages         - lista de idiomas suportados
  GET  /api/plans             - lista de planos (placeholder)
  GET  /                      - frontend (index.html)

Multi-idioma: a partir do parametro `source_lang`/`target_lang` no upload.
Hooks futuros (auth, billing, quotas) estao plugados como dependencias e
placeholders no-op.
"""
from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path
from typing import Optional

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# Garantir import de src/ quando rodando uvicorn app.main:app
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import translate_pdf  # noqa: E402
from src.translator import SUPPORTED_LANGUAGES  # noqa: E402

from .auth import User, get_current_user  # noqa: E402
from .billing import PLANS  # noqa: E402
from .jobs import Job, store  # noqa: E402
from .quotas import QuotaExceeded, check_quota  # noqa: E402

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


STORAGE_DIR = ROOT / "app" / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
INPUT_DIR = STORAGE_DIR / "input"
OUTPUT_DIR = STORAGE_DIR / "output"
INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


app = FastAPI(
    title="Tradutor PDF",
    description="Traducao de PDFs preservando layout (Fase 0 - piloto)",
    version="0.1.0",
)

templates = Jinja2Templates(directory=str(ROOT / "app" / "templates"))


# ---------- Rotas ----------

@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "languages": SUPPORTED_LANGUAGES,
            "plans": PLANS,
        },
    )


@app.get("/api/languages")
def list_languages() -> dict:
    return {"languages": SUPPORTED_LANGUAGES}


@app.get("/api/plans")
def list_plans() -> dict:
    return {"plans": [p.__dict__ for p in PLANS]}


@app.post("/api/translate")
async def create_translation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_lang: str = Form("en"),
    target_lang: str = Form("pt"),
    user: User = Depends(get_current_user),
) -> dict:
    if source_lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"source_lang invalido: {source_lang}")
    if target_lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"target_lang invalido: {target_lang}")
    if source_lang == target_lang:
        raise HTTPException(400, "source_lang e target_lang devem ser diferentes.")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "O arquivo precisa ser um PDF (.pdf).")

    # Cria job e salva upload em disco
    job = store.create(
        input_path="",  # preenchido abaixo
        original_filename=file.filename,
        source_lang=source_lang,
        target_lang=target_lang,
    )

    input_path = INPUT_DIR / f"{job.id}.pdf"
    with input_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    file.file.close()

    output_path = OUTPUT_DIR / f"{job.id}_{target_lang}.pdf"

    store.update(job.id, input_path=str(input_path))

    # Estimativa de paginas para cota (placeholder)
    try:
        check_quota(user, pages_estimate=0)
    except QuotaExceeded as e:
        raise HTTPException(429, str(e))

    background_tasks.add_task(
        _run_translation,
        job_id=job.id,
        input_path=str(input_path),
        output_path=str(output_path),
        source_lang=source_lang,
        target_lang=target_lang,
    )

    return {"job_id": job.id, "status": "pending"}


def _run_translation(
    job_id: str,
    input_path: str,
    output_path: str,
    source_lang: str,
    target_lang: str,
) -> None:
    """Executa o pipeline em background e atualiza o store."""
    store.update(job_id, status="running", stage="Iniciando", progress=0.0)

    def on_progress(stage: str, pct: float) -> None:
        store.update(job_id, stage=stage, progress=pct)

    try:
        result = translate_pdf(
            input_pdf=input_path,
            output_pdf=output_path,
            source_lang=source_lang,
            target_lang=target_lang,
            provider="google",
            fallbacks=["mymemory"],
            on_progress=on_progress,
            request_delay=0.05,  # evita rate-limit do Google Translate
        )
        from datetime import datetime as _dt
        store.update(
            job_id,
            status="done",
            stage="Concluido",
            progress=100.0,
            output_path=output_path,
            page_count=result.page_count,
            span_count=result.span_count,
            cache_hits=result.cache_hits,
            failed_spans=result.failed_blocks,
            finished_at=_dt.utcnow(),
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Falha no job %s", job_id)
        from datetime import datetime as _dt
        store.update(
            job_id,
            status="error",
            stage="Erro",
            error=str(e),
            finished_at=_dt.utcnow(),
        )


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/download")
def download_job(job_id: str) -> FileResponse:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job.status != "done" or not job.output_path:
        raise HTTPException(409, f"Job ainda nao concluido. Status: {job.status}")
    out = Path(job.output_path)
    if not out.exists():
        raise HTTPException(500, "Arquivo de saida nao existe no disco.")
    # Nome amigavel para download
    base = Path(job.original_filename).stem
    download_name = f"{base}_{job.target_lang}.pdf"
    return FileResponse(
        path=str(out),
        media_type="application/pdf",
        filename=download_name,
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
