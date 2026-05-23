"""
Gerenciamento de jobs de traducao.

Fase 0: armazenamento em memoria (dict). Suficiente para piloto.
Futuro: trocar por Postgres + Celery + Redis sem mudar a interface.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Job:
    id: str
    status: str           # 'pending', 'running', 'done', 'error'
    progress: float       # 0.0 a 100.0
    stage: str            # mensagem curta da etapa atual
    source_lang: str
    target_lang: str
    input_path: str
    output_path: Optional[str] = None
    original_filename: str = ""
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    # Estatisticas pos-execucao
    page_count: int = 0
    span_count: int = 0
    cache_hits: int = 0
    failed_spans: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "progress": round(self.progress, 1),
            "stage": self.stage,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "original_filename": self.original_filename,
            "error": self.error,
            "created_at": self.created_at.isoformat() + "Z",
            "finished_at": self.finished_at.isoformat() + "Z" if self.finished_at else None,
            "page_count": self.page_count,
            "span_count": self.span_count,
            "cache_hits": self.cache_hits,
            "failed_spans": self.failed_spans,
            "download_ready": self.status == "done" and self.output_path is not None,
        }


class JobStore:
    """In-memory job store. Thread-safe."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(
        self,
        input_path: str,
        original_filename: str,
        source_lang: str,
        target_lang: str,
    ) -> Job:
        job_id = uuid.uuid4().hex
        job = Job(
            id=job_id,
            status="pending",
            progress=0.0,
            stage="Aguardando inicio",
            source_lang=source_lang,
            target_lang=target_lang,
            input_path=input_path,
            original_filename=original_filename,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for k, v in fields.items():
                if hasattr(job, k):
                    setattr(job, k, v)

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())


# Singleton global do piloto. Em produção, injete via Depends().
store = JobStore()
