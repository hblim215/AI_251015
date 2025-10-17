from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from ..models import Finding, FindingDetail, FindingRef, FormData, PrecheckResponse
from .document_store import DocumentStore, DocumentRecord


class RuleEngine:
    def __init__(self, rules_path: Path, store: DocumentStore):
        self.rules_path = rules_path
        self.store = store
        self.rules: List[Dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        if not self.rules_path.exists():
            self.rules = []
            return
        with self.rules_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or []
            if not isinstance(data, list):
                raise ValueError("rules.yaml must contain a list of rules.")
            self.rules = data

    def evaluate(self, form: FormData) -> PrecheckResponse:
        payload = form.model_dump(exclude_none=True)
        findings: List[Finding] = []
        for rule in self.rules:
            if not self._is_applicable(rule, payload):
                continue
            findings.extend(self._run_checks(rule, payload))
        status = "ok" if not findings else "violations"
        return PrecheckResponse(status=status, findings=findings)

    def _is_applicable(self, rule: Dict[str, Any], form: Dict[str, Any]) -> bool:
        applies = rule.get("applies")
        if not applies:
            return True
        for dotted_path, expected in applies.items():
            values = list(extract_values(form, dotted_path))
            if isinstance(expected, list):
                if not any(value in expected for value in values):
                    return False
            else:
                if expected not in values:
                    return False
        return True

    def _run_checks(self, rule: Dict[str, Any], form: Dict[str, Any]) -> List[Finding]:
        results: List[Finding] = []
        checks = rule.get("checks", {})
        for op_name, config in checks.items():
            handler = OPERATION_HANDLERS.get(op_name)
            if not handler:
                continue
            op_findings = handler(rule, form, config, self.store)
            results.extend(op_findings)
        return results


def build_finding(rule: Dict[str, Any], message: str, details: List[FindingDetail], store: DocumentStore) -> Finding:
    ref_conf = rule.get("ref", {})
    doc = lookup_reference(store, ref_conf)
    severity = rule.get("severity", "error")
    return Finding(
        rule_id=rule.get("id", "rule"),
        message=message or rule.get("description", ""),
        severity=severity,
        ref=FindingRef(
            doc_id=(doc.doc_id if doc else ref_conf.get("doc_id", "")),
            clause=ref_conf.get("clause") or (doc.clause if doc else None),
            page=doc.page if doc else None,
            snippet=doc.snippet if doc else None,
            effective_date=doc.effective_date if doc else None,
            source_path=doc.source_path if doc else ref_conf.get("source_path"),
            image_path=doc.image_path if doc else None,
        ),
        details=details,
    )


def lookup_reference(store: DocumentStore, ref_conf: Dict[str, Any]) -> Optional[DocumentRecord]:
    doc_id = ref_conf.get("doc_id")
    if not doc_id:
        return None
    clause = ref_conf.get("clause")
    return store.lookup(doc_id, clause)


def op_required_fields(rule: Dict[str, Any], form: Dict[str, Any], config: Iterable[str], store: DocumentStore) -> List[Finding]:
    missing: List[FindingDetail] = []
    for path in config or []:
        values = list(extract_values(form, path))
        if not values or all(value in (None, "", []) for value in values):
            missing.append(FindingDetail(field=path, message="필수 입력값 누락"))
    if not missing:
        return []
    message = rule.get("description", "필수 입력값이 누락되었습니다.")
    return [build_finding(rule, message, missing, store)]


def op_required_attachments(rule: Dict[str, Any], form: Dict[str, Any], config: Iterable[Any], store: DocumentStore) -> List[Finding]:
    required = set()
    for entry in config or []:
        if isinstance(entry, dict):
            required.add(entry.get("type"))
        else:
            required.add(entry)
    attachments = form.get("attachments", [])
    present = {att.get("type") for att in attachments if att.get("type")}
    missing = sorted(filter(None, required - present))
    if not missing:
        return []
    details = [FindingDetail(field="attachments", message=f"{attachment} 첨부 필요") for attachment in missing]
    message = rule.get("description", "필수 첨부가 누락되었습니다.")
    return [build_finding(rule, message, details, store)]


def op_conditional_required_attachments(
    rule: Dict[str, Any], form: Dict[str, Any], config: Dict[str, Any], store: DocumentStore
) -> List[Finding]:
    item_filter = config.get("item_filter")
    required_types = set()
    for entry in config.get("types", []):
        if isinstance(entry, dict):
            required_types.add(entry.get("type"))
        else:
            required_types.add(entry)
    required_types = {type_name for type_name in required_types if type_name}
    if not required_types:
        return []
    items = extract_items(form, item_filter)
    if not items:
        return []
    attachments = form.get("attachments", [])
    present = {att.get("type") for att in attachments if att.get("type")}
    missing = sorted(filter(None, required_types - present))
    if not missing:
        return []
    details = [FindingDetail(field="attachments", message=f"{attachment} 첨부 필요") for attachment in missing]
    message = config.get("message") or rule.get("description", "필수 첨부가 누락되었습니다.")
    return [build_finding(rule, message, details, store)]


def op_request_date_lte(rule: Dict[str, Any], form: Dict[str, Any], config: Dict[str, Any], store: DocumentStore) -> List[Finding]:
    field = config.get("field", "request_date")
    raw_value = next(iter(extract_values(form, field)), None)
    limit_value = config.get("value")
    if not raw_value or not limit_value:
        return []
    try:
        actual_date = parse_date(raw_value)
        limit_date = parse_date(limit_value)
    except ValueError:
        return []
    if actual_date <= limit_date:
        return []
    detail = FindingDetail(field=field, message=f"{actual_date.isoformat()} > {limit_date.isoformat()}")
    message = config.get("message") or rule.get("description", "기한을 초과했습니다.")
    return [build_finding(rule, message, [detail], store)]


def op_per_occurrence_cap(rule: Dict[str, Any], form: Dict[str, Any], config: Dict[str, Any], store: DocumentStore) -> List[Finding]:
    limit = config.get("limit")
    if limit is None:
        return []
    field = config.get("field", "amount_total")
    items = extract_items(form, config.get("item_filter"))
    violations: List[FindingDetail] = []
    for item in items:
        value = item.get(field)
        if value is None:
            continue
        try:
            amount = float(value)
        except (TypeError, ValueError):
            continue
        if amount > float(limit):
            context = f"{item.get('merchant') or item.get('description') or '항목'}: {amount:.0f} > {float(limit):.0f}"
            violations.append(FindingDetail(field=f"items[].{field}", message="금액 한도 초과", context=context))
    if not violations:
        return []
    message = config.get("message") or rule.get("description", "한도를 초과했습니다.")
    return [build_finding(rule, message, violations, store)]


def op_pattern(rule: Dict[str, Any], form: Dict[str, Any], config: Dict[str, Any], store: DocumentStore) -> List[Finding]:
    field = config.get("field")
    regex = config.get("regex")
    if not field or not regex:
        return []
    flags = re.IGNORECASE if config.get("ignore_case", True) else 0
    pattern = re.compile(regex, flags)
    values = list(extract_values(form, field))
    failures: List[FindingDetail] = []
    negate = config.get("negate", False)
    for value in values:
        if value is None:
            continue
        matched = bool(pattern.search(str(value)))
        if negate and matched:
            failures.append(FindingDetail(field=field, message="금지된 패턴과 일치", context=str(value)))
        if not negate and not matched:
            failures.append(FindingDetail(field=field, message="허용된 패턴과 일치하지 않음", context=str(value)))
    if not failures:
        return []
    message = config.get("message") or rule.get("description", "패턴 검증 실패")
    return [build_finding(rule, message, failures, store)]


OPERATION_HANDLERS = {
    "required_fields": op_required_fields,
    "required_attachments": op_required_attachments,
    "conditional_required_attachments": op_conditional_required_attachments,
    "request_date_lte": op_request_date_lte,
    "per_occurrence_cap": op_per_occurrence_cap,
    "pattern": op_pattern,
}


def parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    raise ValueError(f"Invalid date value: {value}")


def extract_values(data: Any, path: str) -> Iterable[Any]:
    parts = path.split(".")
    return _extract(data, parts)


def _extract(current: Any, parts: List[str]) -> Iterable[Any]:
    if not parts:
        yield current
        return
    head, *tail = parts
    if head.endswith("[]"):
        key = head[:-2]
        iterable = []
        if isinstance(current, dict):
            iterable = current.get(key, [])
        if isinstance(iterable, list):
            for item in iterable:
                yield from _extract(item, tail)
        return
    if isinstance(current, dict) and head in current:
        yield from _extract(current[head], tail)


def extract_items(form: Dict[str, Any], item_filter: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = form.get("items", [])
    if not isinstance(items, list):
        return []
    if not item_filter:
        return [item for item in items if isinstance(item, dict)]
    filtered: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if _matches_filter(item, item_filter):
            filtered.append(item)
    return filtered


def _matches_filter(item: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
    for key, expected in criteria.items():
        value = item.get(key)
        if isinstance(expected, list):
            if value not in expected:
                return False
        elif isinstance(expected, dict) and "regex" in expected:
            pattern = re.compile(expected["regex"], re.IGNORECASE)
            if not pattern.search(str(value or "")):
                return False
        else:
            if value != expected:
                return False
    return True
