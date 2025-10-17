from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import DocumentSummary, FormData, PrecheckResponse
from .services.document_store import DocumentStore
from .services.rule_engine import RuleEngine

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"

app = FastAPI(
    title="SpendGuard Precheck API",
    version="2.0.0",
    description="AI 기반 지출결의서 사전 검토 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = DocumentStore(
    kb_path=KNOWLEDGE_DIR / "kb.jsonl",
    registry_path=KNOWLEDGE_DIR / "document_registry.json",
)
engine = RuleEngine(rules_path=KNOWLEDGE_DIR / "rules.yaml", store=store)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/precheck", response_model=PrecheckResponse)
async def precheck(payload: FormData) -> PrecheckResponse:
    return engine.evaluate(payload)


@app.get("/documents", response_model=list[DocumentSummary])
async def list_documents() -> list[DocumentSummary]:
    return [DocumentSummary(**summary) for summary in store.list_documents()]


@app.post("/reload")
async def reload_resources() -> dict[str, str]:
    store.reload()
    engine.reload()
    return {"status": "reloaded"}
