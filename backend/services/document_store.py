from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class DocumentRecord:
    doc_id: str
    title: str
    clause: str
    snippet: str
    page: Optional[int]
    effective_date: Optional[str]
    source_path: Optional[str]
    image_path: Optional[str]


class DocumentStore:
    def __init__(self, kb_path: Path, registry_path: Path):
        self.kb_path = kb_path
        self.registry_path = registry_path
        self.records: Dict[Tuple[str, Optional[str]], DocumentRecord] = {}
        self.registry: List[dict] = []
        self.reload()

    def reload(self) -> None:
        self.records.clear()
        if self.kb_path.exists():
            with self.kb_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    payload = json.loads(line)
                    record = DocumentRecord(
                        doc_id=payload.get("doc_id"),
                        title=payload.get("title", ""),
                        clause=payload.get("clause"),
                        snippet=payload.get("snippet", ""),
                        page=payload.get("page"),
                        effective_date=payload.get("effective_date"),
                        source_path=payload.get("source_path"),
                        image_path=payload.get("image_path"),
                    )
                    key = (record.doc_id, record.clause)
                    existing = self.records.get(key)
                    if not existing or self._is_newer(record.effective_date, existing.effective_date):
                        self.records[key] = record
        if self.registry_path.exists():
            with self.registry_path.open("r", encoding="utf-8") as handle:
                try:
                    self.registry = json.load(handle)
                except json.JSONDecodeError:
                    self.registry = []

    def _is_newer(self, left: Optional[str], right: Optional[str]) -> bool:
        if left is None:
            return False
        if right is None:
            return True
        try:
            left_dt = datetime.fromisoformat(left)
        except ValueError:
            left_dt = datetime.min
        try:
            right_dt = datetime.fromisoformat(right)
        except ValueError:
            right_dt = datetime.min
        return left_dt >= right_dt

    def lookup(self, doc_id: str, clause: Optional[str] = None) -> Optional[DocumentRecord]:
        if clause:
            return self.records.get((doc_id, clause)) or self._latest_for_doc(doc_id)
        return self._latest_for_doc(doc_id)

    def _latest_for_doc(self, doc_id: str) -> Optional[DocumentRecord]:
        candidates = [record for (did, _), record in self.records.items() if did == doc_id]
        if not candidates:
            return None
        candidates.sort(key=lambda rec: rec.effective_date or "", reverse=True)
        return candidates[0]

    def list_documents(self) -> Iterable[dict]:
        return self.registry
