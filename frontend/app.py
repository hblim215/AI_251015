from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import Counter

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


def inject_dashboard_styles() -> None:
    st.markdown(
        """
        <style>
        .metric-row {
            display: flex;
            flex-wrap: wrap;
            gap: 18px;
            margin: 12px 0 24px 0;
        }
        .metric-card {
            flex: 1 1 200px;
            padding: 18px 20px;
            border-radius: 20px;
            color: #ffffff;
            box-shadow: 0 12px 24px rgba(14, 27, 71, 0.18);
            backdrop-filter: blur(6px);
        }
        .metric-card h2 {
            margin: 0;
            font-size: 30px;
            font-weight: 700;
        }
        .metric-card span {
            display: block;
            margin-top: 6px;
            font-size: 14px;
            letter-spacing: 0.4px;
            opacity: 0.82;
        }
        .metric-total {
            background: linear-gradient(135deg, #1e2a56, #2f4a7d);
        }
        .metric-error {
            background: linear-gradient(135deg, #ff5c7a, #ff7b5c);
        }
        .metric-warning {
            background: linear-gradient(135deg, #f8b133, #f6c85c);
        }
        .metric-info {
            background: linear-gradient(135deg, #5f8dff, #67c4ff);
        }
        .finding-card {
            background: #ffffff;
            border-radius: 18px;
            padding: 22px 24px;
            margin-bottom: 18px;
            border: 1px solid #eef1f8;
            box-shadow: 0 10px 20px rgba(20, 33, 61, 0.1);
        }
        .finding-card h3 {
            margin: 0;
            font-size: 20px;
            font-weight: 600;
            color: #1e2a56;
        }
        .finding-card p {
            margin: 4px 0 0 0;
            color: #4d5875;
            font-size: 14px;
        }
        .finding-meta {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
            font-size: 15px;
            font-weight: 600;
        }
        .badge {
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 500;
            display: inline-block;
            background: #eef1f8;
            color: #1e2a56;
        }
        .badge-error { background: rgba(255, 92, 122, 0.12); color: #ff3364; }
        .badge-warning { background: rgba(248, 195, 50, 0.16); color: #c98700; }
        .badge-info { background: rgba(96, 182, 255, 0.14); color: #2c7be5; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_summary(findings: List[Dict[str, Any]]) -> None:
    counts = Counter(finding.get("severity", "info") for finding in findings)
    total = len(findings)
    st.markdown(
        f"""
        <div class="metric-row">
            <div class="metric-card metric-total">
                <h2>{total}</h2>
                <span>전체 검토 항목</span>
            </div>
            <div class="metric-card metric-error">
                <h2>{counts.get('error', 0)}</h2>
                <span>심각 (Error)</span>
            </div>
            <div class="metric-card metric-warning">
                <h2>{counts.get('warning', 0)}</h2>
                <span>주의 (Warning)</span>
            </div>
            <div class="metric-card metric-info">
                <h2>{counts.get('info', 0)}</h2>
                <span>알림 (Info)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
        badge_class = f"badge badge-{severity}"
        st.markdown(
            f"""
            <div class="finding-card">
                <div class="finding-meta">
                    <span>{icon}</span>
                    <span class="{badge_class}">{severity.upper()}</span>
                    <span class="badge">{finding.get('rule_id')}</span>
                </div>
                <h3>{finding.get('message', '검토 결과')}</h3>
            """,
            unsafe_allow_html=True,
        )
        details = finding.get("details") or []
        if details:
            detail_lines = []
            for detail in details:
                field = detail.get("field") or "항목"
                message = detail.get("message", "")
                context = f" ({detail.get('context')})" if detail.get("context") else ""
                detail_lines.append(f"<li><strong>{field}</strong> {message}{context}</li>")
            st.markdown("<ul>" + "".join(detail_lines) + "</ul>", unsafe_allow_html=True)
        ref = finding.get("ref") or {}
        ref_lines = []
        if ref.get("doc_id"):
            ref_lines.append(f"문서: <strong>{ref['doc_id']}</strong>")
        if ref.get("effective_date"):
            ref_lines.append(f"시행일: {ref['effective_date']}")
        if ref.get("page"):
            ref_lines.append(f"페이지: {ref['page']}")
        if ref_lines:
            st.markdown("<p>" + " · ".join(ref_lines) + "</p>", unsafe_allow_html=True)
        if ref.get("snippet"):
            st.markdown(f"<blockquote>{ref['snippet']}</blockquote>", unsafe_allow_html=True)
        image_path = ref.get("image_path")
        if image_path:
            image_file = ROOT / image_path
            if image_file.exists():
                st.image(str(image_file), caption="PDF 근거 페이지", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="지출결의서 사전 검토 시스템", layout="wide")
    inject_dashboard_styles()
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
                findings = result.get("findings", [])
                st.success(f"사전 검토 결과: {result.get('status')} (총 {len(findings)}건)")
                if findings:
                    render_summary(findings)
                render_findings(findings)


if __name__ == "__main__":
    main()
