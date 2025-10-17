# Agent Guide

## 프로젝트 요약
- **목적**: 사내 결재서류(지출결의서) 입력값을 최신 규정·공지와 대조하여 누락/위반 항목을 사전 검토.
- **구성**:
  - `ingestion/` : 게시판 공지와 PDF/DOCX 첨부를 색인하여 `knowledge/kb.jsonl` 생성
  - `backend/`   : FastAPI 규칙 엔진, `/precheck`, `/documents`, `/reload`
- `frontend/`  : Streamlit UI (한국어 기준), HAR 업로드 지원, 검토 결과/근거 문서 표시
  - `knowledge/` : 규칙 DSL(`rules.yaml`), 문서 레지스트리 등 메타데이터

## 작업 원칙
1. `docs/` 폴더의 원본 문서(예시 지출결의서, 규정 PDF)는 삭제하지 않는다.
2. 규칙 추가/수정 시 `knowledge/rules.yaml`과 관련 문서 스니펫(`knowledge/kb.jsonl`)을 동시에 갱신한다.
3. 인입 데이터는 항상 최신 버전을 우선 적용한다. `document_registry.json`에 `effective_date`를 기록해 비교한다.
4. 코드/문서는 가능한 한 ASCII를 유지하되, 브랜드 혹은 인용 문장에 한글이 필요하면 허용한다.
5. 테스트 또는 임시 스크립트는 `scripts/` 혹은 `notebooks/`에 분리하고 README에 사용법을 기록한다.

## 실행 절차
```powershell
poetry install
poetry run python ingestion/ingest.py
poetry run uvicorn backend.main:app --reload
poetry run streamlit run frontend/app.py
```

## 규칙 DSL 단축 설명
- `applies.form_type`, `applies.accrual_month` 등으로 대상 범위 지정
- `checks` 항목:
  - `required_fields`
  - `required_attachments`
  - `request_date_lte`
  - `per_occurrence_cap`
  - `pattern`
- `ref`는 `doc_id`, `clause`, `page`, `snippet_id`를 포함하여 근거 문서 연결

## 문서 색인
- `docs/bulletins/`: 게시판 텍스트 파일
- `docs/source_pdfs/`: 규정/공지 PDF
- `ingestion/ingest.py` 실행 시 `knowledge/kb.jsonl`, `knowledge/document_registry.json` 갱신
- PDF는 자동으로 페이지 이미지를 `knowledge/snippets/`에 저장하며, Streamlit에서 근거 이미지를 노출할 수 있습니다.
- OCR이 필요한 PDF는 [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)이 로컬에 설치되어 있어야 텍스트를 추출할 수 있습니다.
- 사내 결재 페이지 데이터는 HAR(또는 API JSON) 업로드 방식으로 `common.doc_parser`를 통해 표준 FormData로 변환합니다.

## 배포 고려 사항
- API 인증/인가 (사내 SSO, JWT)
- 감사 로그 (검토 요청 입력값, 결과 저장)
- 배치 처리 (대량 결의서 업로드)
- 최신 공지 감시 → 규칙 초안 자동화 파이프라인
