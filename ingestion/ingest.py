from __future__ import annotations

import io
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
KNOWLEDGE_DIR = ROOT / "knowledge"
TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
DEFAULT_OCR_LANG = "kor+eng"
DEFAULT_RENDER_ZOOM = 2.0
TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
DEFAULT_OCR_LANG = "kor+eng"
DEFAULT_RENDER_ZOOM = 2.0


@dataclass
class DocumentSegment:
    doc_id: str
    title: str
    clause: str
    snippet: str
    source_path: str
    page: Optional[int]
    effective_date: Optional[str]
    extracted_at: str
    image_path: Optional[str] = None


@dataclass
class DocumentSummary:
    doc_id: str
    title: str
    effective_date: Optional[str]
    source_path: str
    segments: int
    extracted_at: str


def slugify(value: str) -> str:
    lowered = value.lower()
    slug = re.sub(r"[^0-9a-z]+", "-", lowered)
    slug = slug.strip("-")
    if slug:
        return slug
    hex_digest = value.encode("utf-8").hex()
    return f"doc-{hex_digest[:12]}"


def extract_effective_date(name: str) -> Optional[str]:
    pattern = re.compile(r"(20\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?([0-3]\d)")
    match = pattern.search(name)
    if not match:
        return None
    year, month, day = match.groups()
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except ValueError:
        return None


def read_text_with_fallback(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_bulletins() -> Iterator[DocumentSegment]:
    bulletin_dir = DOCS_DIR / "bulletins"
    if not bulletin_dir.exists():
        return iter(())
    for path in sorted(bulletin_dir.glob("*.txt")):
        text = read_text_with_fallback(path)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        doc_id = f"bulletin/{slugify(path.stem)}"
        effective_date = extract_effective_date(path.stem)
        extracted_at = datetime.utcnow().isoformat()
        for idx, paragraph in enumerate(paragraphs, start=1):
            clause = f"paragraph-{idx}"
            yield DocumentSegment(
                doc_id=doc_id,
                title=paragraphs[0][:80] if paragraphs else path.stem,
                clause=clause,
                snippet=paragraph,
                source_path=str(path.relative_to(ROOT)),
                page=None,
                effective_date=effective_date,
                extracted_at=extracted_at,
            )


def parse_pdfs() -> Iterator[DocumentSegment]:
    pdf_dir = DOCS_DIR / "source_pdfs"
    if not pdf_dir.exists():
        return iter(())
    for path in sorted(pdf_dir.glob("*.pdf")):
        doc = fitz.open(path)  # type: ignore[arg-type]
        doc_id = f"pdf/{slugify(path.stem)}"
        effective_date = extract_effective_date(path.stem)
        extracted_at = datetime.utcnow().isoformat()
        title = path.stem
        snippet_images: dict[int, str] = {}
        for index in range(doc.page_count):
            page = doc.load_page(index)
            matrix = fitz.Matrix(DEFAULT_RENDER_ZOOM, DEFAULT_RENDER_ZOOM)
            pix = page.get_pixmap(matrix=matrix)
            text_content = page.get_text("text").strip()
            ocr_content = run_ocr_on_pixmap(pix)
            combined_parts: List[str] = []
            for part in (text_content, ocr_content):
                if part and part not in combined_parts:
                    combined_parts.append(part)
            if combined_parts:
                combined_text = "\n".join(combined_parts)
                snippets = split_text(combined_text)
            else:
                snippets = ["텍스트 추출 실패: PDF 페이지 이미지를 참고하세요."]
            if index not in snippet_images:
                image_rel = render_page_image(pix, path, index)
                snippet_images[index] = image_rel
            for offset, snippet in enumerate(snippets, start=1):
                clause = f"page-{index + 1}-segment-{offset}"
                yield DocumentSegment(
                    doc_id=doc_id,
                    title=title,
                    clause=clause,
                    snippet=snippet,
                    source_path=str(path.relative_to(ROOT)),
                    page=index + 1,
                    effective_date=effective_date,
                    extracted_at=extracted_at,
                    image_path=snippet_images.get(index),
                )
        doc.close()


def run_ocr_on_pixmap(pix: fitz.Pixmap, lang: str = DEFAULT_OCR_LANG) -> str:
    if not TESSERACT_AVAILABLE:
        return ""
    try:
        image_bytes = pix.tobytes("png")
        with Image.open(io.BytesIO(image_bytes)) as image:
            text = pytesseract.image_to_string(image, lang=lang)
            return text.strip()
    except Exception:
        return ""


def render_page_image(pix: fitz.Pixmap, pdf_path: Path, page_index: int) -> Optional[str]:
    try:
        image_bytes = pix.tobytes("png")
    except Exception:
        return None
    snippets_dir = KNOWLEDGE_DIR / "snippets"
    snippets_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(pdf_path.stem)
    filename = f"{slug}_p{page_index + 1}.png"
    output_path = snippets_dir / filename
    output_path.write_bytes(image_bytes)
    return str(output_path.relative_to(ROOT))


def split_text(text: str, max_len: int = 480) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    segments: List[str] = []
    buffer = ""
    for sentence in sentences:
        candidate = f"{buffer} {sentence}".strip()
        if len(candidate) > max_len and buffer:
            segments.append(buffer.strip())
            buffer = sentence
        else:
            buffer = candidate
    if buffer:
        segments.append(buffer.strip())
    return segments or [text[:max_len]]


def build_registry(segments: Iterable[DocumentSegment]) -> List[DocumentSummary]:
    registry: dict[str, DocumentSummary] = {}
    for segment in segments:
        summary = registry.get(segment.doc_id)
        if summary:
            summary.segments += 1
            if (segment.effective_date or "") > (summary.effective_date or ""):
                summary.effective_date = segment.effective_date
        else:
            registry[segment.doc_id] = DocumentSummary(
                doc_id=segment.doc_id,
                title=segment.title,
                effective_date=segment.effective_date,
                source_path=segment.source_path,
                segments=1,
                extracted_at=segment.extracted_at,
            )
    return list(registry.values())


def write_outputs(segments: List[DocumentSegment], summaries: List[DocumentSummary]) -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    (KNOWLEDGE_DIR / "snippets").mkdir(parents=True, exist_ok=True)
    kb_path = KNOWLEDGE_DIR / "kb.jsonl"
    registry_path = KNOWLEDGE_DIR / "document_registry.json"

    with kb_path.open("w", encoding="utf-8") as handle:
        for segment in segments:
            handle.write(json.dumps(asdict(segment), ensure_ascii=False))
            handle.write("\n")

    with registry_path.open("w", encoding="utf-8") as handle:
        json.dump([asdict(summary) for summary in summaries], handle, ensure_ascii=False, indent=2)


def main() -> None:
    all_segments = list(parse_bulletins()) + list(parse_pdfs())
    if not all_segments:
        print("No documents found. Ensure docs/bulletins or docs/source_pdfs contain files.")
        return
    summaries = build_registry(all_segments)
    write_outputs(all_segments, summaries)
    print(f"Wrote {len(all_segments)} segments across {len(summaries)} documents.")


if __name__ == "__main__":
    main()
