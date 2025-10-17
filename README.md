# AI 기반 지출결의서 사전 검토 시스템

SpendGuard 2.0은 사내 게시판·문서함에서 최신 규정과 공지를 자동으로 색인하고, 지출결의서 입력값을 규정에 맞춰 선제적으로 점검하는 Python 기반 솔루션입니다.

## 핵심 목표
- **최신 규정 반영**: 재무톡톡 등 게시판의 공지, 전사 문서함 PDF·DOCX 첨부를 수집해 조항·기한 정보를 추출합니다.
- **문서 근거 제공**: 검토 결과마다 어떤 문서·페이지·조항을 참고했는지 즉시 확인할 수 있는 스니펫을 제공합니다.
- **실시간 사전 검토**: 사용자가 결재 양식 입력을 마치면 누락/위반 항목을 즉시 알리고 수정 방향을 안내합니다.

## 프로젝트 구조
```
backend/        FastAPI 백엔드 (규칙 평가 API, 문서 조회)
frontend/       Streamlit 기반 사전 검토 UI
ingestion/      게시판·문서 파싱 및 지식베이스 생성 스크립트
knowledge/      색인 결과 및 규칙 DSL (kb.jsonl, rules.yaml 등)
docs/           원본 PDF/첨부/게시판 스냅샷, UI 참고 스크린샷
```

## 빠른 실행
```powershell
cd C:\Users\user\Desktop\AI_251015
poetry install

# 1) 지식베이스 색인
poetry run python ingestion/ingest.py

# 2) 백엔드 API
poetry run uvicorn backend.main:app --reload

# 3) Streamlit UI (새 터미널)
poetry run streamlit run frontend/app.py
```
- 브라우저에서 `http://localhost:8501`에 접속해 양식 정보를 입력하고 **검토** 버튼을 누르면 `/precheck` 결과가 카드로 표시됩니다.
- API는 `http://127.0.0.1:8000`에서 동작하며 `/docs` 경로로 OpenAPI 문서를 확인할 수 있습니다.

## 문서 색인 파이프라인
1. `ingestion/ingest.py`가 `docs/bulletins/`, `docs/source_pdfs/` 등을 순회합니다.
2. 텍스트·PDF·DOCX에 대해 공통 `DocumentSegment` 구조로 조항/페이지/효력일자를 추출합니다.
3. 최신 문서만 남도록 `document_registry.json`에서 버전 비교 후 `knowledge/kb.jsonl`에 기록합니다.
4. PDF는 페이지 단위 이미지를 `knowledge/snippets/`에 저장하므로, 근거 문서를 Streamlit에서 바로 확인할 수 있습니다.
5. 결과는 FastAPI가 기동될 때 메모리로 적재되어 규칙 평가 시 참조됩니다.

> 현재 샘플 데이터는 `docs/bulletins/2025-09-finance-close.txt` 공지와 `docs/source_pdfs/` 내 PDF 세 건을 기반으로 합니다.

> **OCR 의존성**  
> 이미지 기반 PDF까지 분석하려면 [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)을 로컬에 설치해야 합니다.  
> - Windows: `choco install tesseract`  
> - macOS: `brew install tesseract`

## 규칙 DSL 개요 (`knowledge/rules.yaml`)
- `applies`: 폼 타입·귀속월 등 조건부 적용 영역
- `checks`: `required_fields`, `request_date_lte`, `per_occurrence_cap`, `required_attachments` 등의 연산
- `ref`: `doc_id`, `clause`, `page`, `snippet_id`로 근거 문서 매핑

규칙은 YAML로 관리되며 재무 규정 변경 시 Git 히스토리로 추적할 수 있습니다.

## Streamlit UI
- `docs/screenshots/ui_placeholder.png` 참고 레이아웃을 적용했습니다.
- 좌측 사이드바에서 결의서 필수 정보를 직접 입력하거나, 회사 결재 시스템에서 추출한 HAR 파일을 업로드하여 자동으로 값을 채울 수 있습니다.
- 검토 결과는 심각도(❌/⚠/ℹ) 아이콘과 함께 근거 문서를 바로 펼쳐볼 수 있도록 구성했습니다.
- HAR 추출 절차: `F12 → Network` 탭에서 결재서를 임시 저장한 뒤 해당 요청을 **Save all as HAR with content**로 저장합니다.

## 향후 과제
- 전사 게시판 API 연동 및 SSO 인증
- LLM 기반 자연어 추론 추가 (예: 첨부 설명에서 자동 필드 추출)
- 지속적인 규정 모니터링 및 알림 (신규 공지 → 규칙 초안 자동 생성)

자세한 설계와 백로그는 `ARCHITECTURE.md`, `TODO.md` 문서를 참고하세요.
