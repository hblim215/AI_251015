from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.doc_parser import document_to_form, extract_document_from_har

DEFAULT_API = os.getenv("PRECHECK_API_URL", "http://localhost:8000")
API_PRECHECK = f"{DEFAULT_API.rstrip('/')}/precheck"
API_DOCUMENTS = f"{DEFAULT_API.rstrip('/')}/documents"

PLACEHOLDER_IMAGE = ROOT / "docs" / "screenshots" / "ui_placeholder.png"

SAMPLE_PAYLOAD: Dict[str, Any] = {
    "form_type": "card_expense",
    "title": "9월 야근 식대 청구",
    "company_code": "HQ01",
    "department_code": "FINANCE-TEAM1",
    "drafter_name": "김애널",
    "accrual_month": "2025-09",
    "request_date": "2025-10-02",
    "pay_request_date": "2025-10-12",
    "project_code": "PRJ-OPS-25",
    "items": [
        {
            "use_date": "2025-09-28",
            "category": "meal_overtime",
            "merchant": "야근식당",
            "amount_total": 19800,
            "description": "프로젝트 야근 식사",
            "headcount": 2,
        }
    ],
    "attachments": [
        {"filename": "receipt_20250928.pdf", "type": "card_receipt"},
    ],
}

ICON_BY_SEVERITY = {"error": "❌", "warning": "⚠", "info": "ℹ"}


def load_documents() -> List[Dict[str, Any]]:
    try:
        response = requests.get(API_DOCUMENTS, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return []


def build_form_payload() -> Dict[str, Any]:
    st.sidebar.subheader("결의서 기본 정보")
    form_type = st.sidebar.selectbox(
        "결의 구분",
        ["card_expense", "trip_expense", "vendor_invoice", "dispatch_allowance"],
        index=0,
    )
    title = st.sidebar.text_input("제목", value="지출결의서 초안")
    company_code = st.sidebar.text_input("회사 코드", value="HQ01")
    department_code = st.sidebar.text_input("부서 코드", value="FINANCE")
    drafter_name = st.sidebar.text_input("기안자", value="홍길동")
    accrual_month = st.sidebar.text_input("귀속 월 (YYYY-MM)", value="2025-09")
    request_date_value = st.sidebar.date_input("기안일", value=date(2025, 10, 1))
    pay_request_date_value = st.sidebar.date_input("지급 요청일", value=date(2025, 10, 10))
    project_code = st.sidebar.text_input("프로젝트 코드", value="PRJ-TEST")

    st.sidebar.subheader("지출 내역")
    items_df = st.sidebar.data_editor(
        pd.DataFrame(
            [
                {
                    "use_date": "2025-09-28",
                    "category": "meal_overtime",
                    "merchant": "야근식당",
                    "amount_total": 19800,
                    "description": "야근 식사",
                }
            ]
        ),
        num_rows="dynamic",
        use_container_width=True,
        key="items_editor",
    )

    st.sidebar.subheader("첨부")
    attachments_df = st.sidebar.data_editor(
        pd.DataFrame(
            [
                {"filename": "receipt.pdf", "type": "card_receipt"},
            ]
        ),
        num_rows="dynamic",
        use_container_width=True,
        key="attachments_editor",
    )

    payload: Dict[str, Any] = {
        "form_type": form_type,
        "title": title,
        "company_code": company_code,
        "department_code": department_code,
        "drafter_name": drafter_name,
        "accrual_month": accrual_month,
        "request_date": request_date_value.isoformat() if isinstance(request_date_value, date) else request_date_value,
        "pay_request_date": pay_request_date_value.isoformat()
        if isinstance(pay_request_date_value, date)
        else pay_request_date_value,
        "project_code": project_code,
        "items": clean_records(items_df.to_dict("records")),
        "attachments": clean_records(attachments_df.to_dict("records")),
    }
    return payload


def clean_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for record in records:
        if not any(value not in (None, "", []) for value in record.values()):
            continue
        cleaned.append({key: convert_value(value) for key, value in record.items() if value not in ("", None)})
    return cleaned


def convert_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def load_corp_form_payload() -> Optional[Dict[str, Any]]:
    uploaded = st.sidebar.file_uploader("HAR 파일 업로드", type=["har", "json"])
    if not uploaded:
        st.sidebar.caption("결재 페이지에서 HAR 파일을 저장해 업로드하세요.")
        return None
    raw_bytes = uploaded.read()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = raw_bytes.decode("cp949", errors="ignore")
    try:
        if uploaded.name.endswith(".har"):
            document = extract_document_from_har(text)
        else:
            raw = json.loads(text)
            document = raw.get("document", raw)
    except Exception as exc:
        st.sidebar.error(f"사내 양식 데이터를 해석할 수 없습니다: {exc}")
        return None
    try:
        payload = document_to_form(document)
    except Exception as exc:
        st.sidebar.error(f"결재 양식을 폼 데이터로 변환하지 못했습니다: {exc}")
        return None
    st.sidebar.success("사내 양식 데이터를 불러왔습니다.")
    return payload


def get_payload(source: str) -> Optional[Dict[str, Any]]:
    if source == "수기 입력":
        return build_form_payload()
    if source == "사내 양식(HAR)":
        return load_corp_form_payload()
    if source == "샘플 시나리오":
        st.sidebar.info("샘플 데이터를 불러왔습니다.")
        return SAMPLE_PAYLOAD
    return None


def call_precheck(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    body = {key: value for key, value in payload.items() if key != "meta"}
    try:
        response = requests.post(API_PRECHECK, json=body, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"사전 검토 요청이 실패했습니다: {exc}")
        return None


def render_findings(findings: List[Dict[str, Any]]) -> None:
    if not findings:
        st.success("위반 사항이 없습니다. 모든 항목이 규정에 부합합니다.")
        return
    for finding in findings:
        severity = finding.get("severity", "info")
        icon = ICON_BY_SEVERITY.get(severity, "ℹ")
        st.markdown(f"### {icon} {finding.get('message', '검토 결과')}")
        st.caption(f"규칙 ID: `{finding.get('rule_id')}` · 심각도: {severity}")
        details = finding.get("details") or []
        if details:
            with st.expander("세부 정보"):
                for detail in details:
                    field = detail.get("field") or "항목"
                    message = detail.get("message")
                    context = detail.get("context")
                    st.write(f"- **{field}**: {message}")
                    if context:
                        st.caption(context)
        ref = finding.get("ref") or {}
        with st.expander("근거 문서", expanded=False):
            st.write(f"문서: {ref.get('doc_id', 'N/A')}")
            if ref.get("effective_date"):
                st.write(f"시행일: {ref['effective_date']}")
            if ref.get("page"):
                st.write(f"페이지: {ref['page']}")
            if ref.get("snippet"):
                st.markdown(f"> {ref['snippet']}")
            if ref.get("source_path"):
                st.caption(f"Source: {ref['source_path']}")
            image_path = ref.get("image_path")
            if image_path:
                image_file = ROOT / image_path
                if image_file.exists():
                    st.image(str(image_file), caption="PDF 근거 페이지", use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="지출결의서 사전 검토 시스템", layout="wide")
    if PLACEHOLDER_IMAGE.exists():
        st.image(str(PLACEHOLDER_IMAGE), width=900)
    st.title("지출결의서 사전 검토 시스템")
    st.caption("최신 재무 공지와 규정을 토대로 결재서류 누락 요소를 자동 점검합니다.")

    documents = load_documents()
    if documents:
        with st.expander("최근 참조 문서"):
            for doc in documents:
                st.write(
                    f"- **{doc.get('title')}** · doc_id: `{doc.get('doc_id')}` · 시행일: {doc.get('effective_date')}"
                )

    st.sidebar.title("입력 방식")
    source = st.sidebar.radio("데이터 선택", options=["수기 입력", "사내 양식(HAR)", "샘플 시나리오"], index=0)
    payload = get_payload(source)

    st.subheader("전송 데이터 미리보기")
    if payload:
        st.json(payload)
        if payload.get("items"):
            st.subheader("결의 내역 요약")
            item_frame = pd.DataFrame(payload["items"])
            display_cols = {
                "category": "적요",
                "use_date": "사용일자",
                "merchant": "거래처",
                "amount_total": "합계",
                "card_type": "카드유형",
            }
            existing = {col: alias for col, alias in display_cols.items() if col in item_frame.columns}
            summary = item_frame[list(existing.keys())].rename(columns=existing)
            if "합계" in summary.columns:
                summary["합계"] = summary["합계"].apply(lambda v: f"{int(v):,}" if pd.notnull(v) else "")
            st.dataframe(summary, use_container_width=True)
    else:
        st.info("사이드바에서 결재서를 입력하거나 HAR 파일을 업로드하세요.")

    if st.button("검토", type="primary", disabled=payload is None):
        if payload is None:
            st.warning("검토할 데이터가 없습니다.")
        else:
            with st.spinner("사전 검토를 진행 중입니다..."):
                result = call_precheck(payload)
            if result:
                st.success(f"사전 검토 결과: {result.get('status')}")
                render_findings(result.get("findings", []))


if __name__ == "__main__":
    main()
