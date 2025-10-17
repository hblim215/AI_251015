from __future__ import annotations

import base64
import json
import re
from datetime import date, datetime, time
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup


def _extract_document_from_text(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        if isinstance(data.get("document"), dict):
            return data["document"]
        if "docBodyContent" in data:
            return data
    return None


def extract_document_from_har(har_text: str) -> Dict[str, Any]:
    """Extract the most recent approval document payload from a HAR file."""
    har = json.loads(har_text)
    entries: Iterable[dict] = har.get("log", {}).get("entries", [])
    # Prefer PUT/POST payloads (tempsave)
    for entry in reversed(list(entries)):
        request = entry.get("request", {})
        method = (request.get("method") or "").upper()
        url = request.get("url", "")
        if method not in {"PUT", "POST"}:
            continue
        if "/api/approval/document" not in url:
            continue
        payload = (request.get("postData") or {}).get("text")
        if not payload:
            continue
        document = _extract_document_from_text(payload)
        if document:
            return document
    # Fallback: check responses (e.g., GET /document/{id})
    for entry in reversed(list(entries)):
        response = entry.get("response", {})
        content = response.get("content") or {}
        text = content.get("text")
        if not text:
            continue
        if content.get("encoding") == "base64":
            try:
                text = base64.b64decode(text).decode("utf-8")
            except Exception:
                continue
        document = _extract_document_from_text(text)
        if document:
            return document
    raise ValueError("HAR 파일에서 결재 문서 payload를 찾지 못했습니다.")


def document_to_form(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DaouOffice approval document data into FormData JSON."""
    html = document.get("docBodyContent")
    if not html:
        raise ValueError("document 객체에 docBodyContent가 없습니다.")
    soup = BeautifulSoup(html, "html.parser")

    title = extract_text_by_id(soup, "subject")
    heading = soup.find("td", class_="title")
    heading_text = heading.get_text(strip=True) if heading else title

    drafter_dept = extract_text_by_id(soup, "draftDept")
    drafter_name = extract_text_by_id(soup, "draftUser")
    draft_date = parse_korean_date(extract_text_by_id(soup, "draftDate"))
    pay_request_str = extract_text_by_id(soup, "editorForm_12")
    pay_request_date = parse_korean_date(pay_request_str)

    company_name = extract_text_by_id(soup, "editorForm_5")
    card_account = extract_text_by_id(soup, "editorForm_8")

    items = parse_slip_table(soup)
    accrual_month = compute_accrual_month(items)

    form_type = resolve_form_type(heading_text)

    form_payload: Dict[str, Any] = {
        "form_type": form_type,
        "title": title or heading_text,
        "company_code": company_name or None,
        "department_code": drafter_dept or None,
        "drafter_name": drafter_name or None,
        "accrual_month": accrual_month,
        "request_date": draft_date.isoformat() if draft_date else None,
        "pay_request_date": pay_request_date.isoformat() if pay_request_date else None,
        "project_code": None,
        "items": items,
        "attachments": [],
    }

    # include payment account if available
    if card_account:
        form_payload.setdefault("meta", {})["payment_account"] = card_account

    return form_payload


def extract_text_by_id(soup: BeautifulSoup, data_id: str) -> str:
    span = soup.find(attrs={"data-id": data_id})
    if not span:
        return ""
    value = span.get("data-value")
    if value:
        return value.strip()
    return span.get_text(strip=True)


def parse_korean_date(value: str) -> Optional[date]:
    if not value:
        return None
    cleaned = re.sub(r"\(.*?\)", "", value).strip()
    if not cleaned:
        return None
    for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def parse_slip_table(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    table = soup.find("table", id="slipBplTable")
    if not table:
        return []
    rows = table.find_all("tr")
    items: List[Dict[str, Any]] = []
    i = 0
    while i < len(rows):
        row = rows[i]
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if is_item_header_row(cells):
            item = build_item_from_rows(cells, rows, i)
            if item:
                items.append(item)
            # skip header + detail rows (and optional description row)
            skip = 2
            if i + 2 < len(rows) and is_description_row(rows[i + 2]):
                skip = 3
                # set description if available
                description_cell = rows[i + 2].find_all("td")
                if item and len(description_cell) > 1:
                    desc_text = description_cell[1].get_text(strip=True)
                    if desc_text:
                        item["description"] = desc_text
            i += skip
            continue
        i += 1
    return items


def is_item_header_row(cells: List[str]) -> bool:
    if len(cells) < 6:
        return False
    if cells[1] in {"기본적요", "상세내용", ""}:
        return False
    if cells[0] not in {"", " "}:
        return False
    return True


def is_description_row(row) -> bool:
    cells = [td.get_text(strip=True) for td in row.find_all("td")]
    return len(cells) >= 2 and cells[0] == "상세내용"


def build_item_from_rows(header: List[str], rows: List[Any], idx: int) -> Optional[Dict[str, Any]]:
    detail_cells = []
    if idx + 1 < len(rows):
        detail_cells = [td.get_text(strip=True) for td in rows[idx + 1].find_all("td")]

    category = header[1]
    card_type = header[2]
    use_date = parse_korean_date(header[3])
    approval_time = parse_time(header[4])
    card_name = header[5] or None

    project = detail_cells[0] if len(detail_cells) > 0 else None
    merchant = detail_cells[1] if len(detail_cells) > 1 else None
    amount_net = parse_number(detail_cells[3] if len(detail_cells) > 3 else None)
    vat_amount = parse_number(detail_cells[4] if len(detail_cells) > 4 else None)
    total_amount = parse_number(detail_cells[5] if len(detail_cells) > 5 else None)

    description_parts = [part for part in (project, merchant) if part]
    description = " / ".join(description_parts) if description_parts else None

    item: Dict[str, Any] = {
        "category": category or None,
        "card_type": card_type or None,
        "merchant": merchant or None,
        "description": description,
        "amount_net": amount_net,
        "vat_amount": vat_amount,
        "amount_total": total_amount,
    }
    if card_name:
        item["card_name"] = card_name
    if use_date:
        item["use_date"] = use_date.isoformat()
    if approval_time and use_date:
        item["approval_time"] = datetime.combine(use_date, approval_time).isoformat()
    elif approval_time:
        item["approval_time"] = approval_time.isoformat()
    return item


def parse_number(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    cleaned = value.replace(",", "").replace("원", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_time(value: Optional[str]) -> Optional[time]:
    if not value:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def compute_accrual_month(items: List[Dict[str, Any]]) -> Optional[str]:
    dates: List[date] = []
    for item in items:
        use_date = item.get("use_date")
        if not use_date:
            continue
        try:
            dates.append(datetime.strptime(use_date, "%Y-%m-%d").date())
        except ValueError:
            continue
    if not dates:
        return None
    earliest = min(dates)
    return earliest.strftime("%Y-%m")


def resolve_form_type(heading: Optional[str]) -> str:
    if not heading:
        return "card_expense"
    if "법인카드" in heading:
        return "card_expense"
    if "출장" in heading or "파견" in heading:
        return "trip_expense"
    return "card_expense"
