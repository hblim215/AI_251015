# SpendGuard 2.0 Architecture

## 1. 전체 흐름

```
게시판/문서함 → Ingestion 파이프라인 → knowledge/kb.jsonl → FastAPI Rule Engine → Streamlit UI
```

1. **Ingestion**
   - `docs/bulletins/`의 TXT/HTML, `docs/source_pdfs/`의 PDF, 향후 DOCX를 스캔
   - PyMuPDF/`python-docx`로 텍스트와 페이지 메타데이터를 추출
   - 규정마다 `doc_id`, `effective_date`, `clause`, `snippet`을 생성
   - 최신 버전만 남기고 `knowledge/kb.jsonl`에 저장, `document_registry.json`으로 관리

2. **Rule Registry**
   - `knowledge/rules.yaml`에 DSL 형태로 규칙 정의
   - `applies` → 폼 유형/귀속월/항목 조건
   - `checks` → `required_fields`, `request_date_lte`, `per_occurrence_cap`, `required_attachments`, `regex` 등
   - `ref` → 근거 문서 정보(`doc_id`, `clause`, `page`, `snippet_id`)

3. **Backend (FastAPI)**
   - `/precheck`: Form JSON을 받아 규칙 엔진에 전달
   - `/documents`: 최신 규정 목록과 스니펫 검색
   - `/reload`: 규칙·지식베이스 재로딩
   - 서비스 계층:
     - `DocumentStore` → `kb.jsonl` 로드, doc_id/클러스터 관리
     - `RuleEngine` → DSL을 해석해 검증 실행
     - `BulletinService` → 최근 공지 노출용 API (Plan)

4. **Frontend (Streamlit)**
   - `docs/screenshots/ui_placeholder.png` 레이아웃 기반
   - 사이드바에 결의서 필드 입력, HAR 업로드, 본문에는 공지 배너·검토 버튼·결과 카드
   - `/precheck` 호출 결과를 즉시 표시하고, `ref` 정보로 근거 스니펫을 모달/Hover에서 제공

## 2. 데이터 모델

### FormData (요청)
```json
{
  "form_type": "card_expense",
  "accrual_month": "2025-09",
  "request_date": "2025-10-02",
  "pay_request_date": "2025-10-10",
  "items": [
    {"category": "meal_overtime", "amount_total": 18000, "description": "프로젝트 야근"}
  ],
  "attachments": [{"type": "card_receipt", "filename": "receipt.pdf"}]
}
```

### Finding (응답)
```json
{
  "rule_id": "closing_2025_09_cutoff",
  "message": "2025-09 귀속 경비는 10/1 이전에 제출해야 합니다.",
  "severity": "error",
  "ref": {
    "doc_id": "bulletin/2025-09-finance-close",
    "clause": "귀속 월 마감 기한",
    "page": null,
    "snippet": "귀속 월(2025.09) 마감 기한(2025.10.01 ...)"
  },
  "details": [
    {"field": "request_date", "message": "2025-10-02 > 2025-10-01"}
  ]
}
```

## 3. 규칙 엔진 설계

| 연산                | 설명 | 설정 예시 |
|--------------------|------|----------|
| `required_fields`  | 필수 값 확인 | `["project_code", "items[].amount_total"]` |
| `required_attachments` | 첨부 종류 확인 | `["card_receipt", {"type": "timesheet_proof"}]` |
| `request_date_lte` | 날짜 비교 | `{ field: "request_date", value: "2025-10-01" }` |
| `per_occurrence_cap` | 금액 한도 | `{ item_filter: {category: "meal_overtime"}, limit: 12000 }` |
| `pattern`          | 문자열 패턴 | `{ field: "items[].description", regex: "(야근|overtime)" }` |

각 연산은 `RuleEngine` 내에서 함수로 매핑되며, `DocumentStore`를 통해 참조 스니펫을 결합합니다.

## 4. 향후 확장
- **Bulletin Crawler**: 게시판 API → SSO 인증 → 증분 수집
- **LLM Summaries**: 신규 공지 자동 요약 및 규칙 후보 생성
- **Excel/CSV 업로드**: 다중 결의서 배치 검토
- **Role-based Access**: 대시보드 접근 제어 및 검토 이력 저장 (PostgreSQL)

## 5. 테스트 전략
- `pytest` 기반 단위 테스트: 규칙별 성공/실패 케이스, 문서 검색 정확도
- Streamlit E2E: `pytest-playwright`로 UI 자동 검증 (향후)
- Ingestion 리그레션: 샘플 PDF/공지에 대해 추출 결과를 스냅샷 테스트로 고정
