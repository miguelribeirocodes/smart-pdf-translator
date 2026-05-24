"""
Store de glossarios tecnico.

Fase 1: persistencia em arquivo JSON por glossario (app/storage/glossaries/).
Futuro: trocar por Postgres sem mudar a interface.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Optional

from src.glossary import Glossary

log = logging.getLogger(__name__)


class GlossaryStore:
    """
    Store de glossarios persistente em disco (JSON por arquivo).
    Thread-safe.

    Estrutura em disco:
        app/storage/glossaries/
            <id>.json   -- um arquivo por glossario
    """

    def __init__(self, storage_dir: Path) -> None:
        self._dir = storage_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, name: str, terms: dict[str, str]) -> Glossary:
        """Cria e persiste um novo glossario."""
        gid = uuid.uuid4().hex
        g = Glossary(terms=terms, name=name, gid=gid)
        with self._lock:
            g.save(self._dir / f"{gid}.json")
        log.info("Glossario criado: %r (%d termos)", name, len(g))
        return g

    def get(self, gid: str) -> Optional[Glossary]:
        """Carrega um glossario pelo ID. Retorna None se nao existir."""
        path = self._dir / f"{gid}.json"
        if not path.exists():
            return None
        with self._lock:
            try:
                return Glossary.load(path)
            except Exception as e:  # noqa: BLE001
                log.error("Erro ao carregar glossario %s: %s", gid, e)
                return None

    def list_all(self) -> list[dict]:
        """Retorna lista de {id, name, term_count} de todos os glossarios."""
        result = []
        with self._lock:
            for p in sorted(self._dir.glob("*.json")):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    result.append({
                        "id": data.get("id", p.stem),
                        "name": data.get("name", ""),
                        "term_count": len(data.get("terms", {})),
                    })
                except Exception:  # noqa: BLE001
                    pass
        return result

    def update(self, gid: str, name: Optional[str], terms: Optional[dict[str, str]]) -> Optional[Glossary]:
        """Atualiza nome e/ou termos de um glossario existente."""
        g = self.get(gid)
        if g is None:
            return None
        current = g.to_dict()
        new_name = name if name is not None else current["name"]
        new_terms = terms if terms is not None else current["terms"]
        updated = Glossary(terms=new_terms, name=new_name, gid=gid)
        with self._lock:
            updated.save(self._dir / f"{gid}.json")
        return updated

    def delete(self, gid: str) -> bool:
        """Remove um glossario do disco. Retorna True se existia."""
        path = self._dir / f"{gid}.json"
        with self._lock:
            if path.exists():
                path.unlink()
                return True
        return False

    def path_for(self, gid: str) -> Optional[str]:
        """Retorna o caminho absoluto do arquivo JSON de um glossario, ou None."""
        path = self._dir / f"{gid}.json"
        return str(path) if path.exists() else None
