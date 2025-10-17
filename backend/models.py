from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

FormType = Literal["card_expense", "trip_expense", "vendor_invoice", "dispatch_allowance"]


class Attachment(BaseModel):
    filename: str
    type: Optional[str] = None


class Item(BaseModel):
    use_date: Optional[date] = None
    category: Optional[str] = None
    merchant: Optional[str] = None
    amount_net: Optional[float] = None
    vat_amount: Optional[float] = None
    amount_total: Optional[float] = None
    approval_time: Optional[datetime] = None
    card_type: Optional[str] = None
    description: Optional[str] = None
    headcount: Optional[int] = None


class FormData(BaseModel):
    form_type: FormType
    title: Optional[str] = None
    company_code: Optional[str] = None
    department_code: Optional[str] = None
    drafter_name: Optional[str] = None
    accrual_month: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    request_date: Optional[date] = None
    pay_request_date: Optional[date] = None
    project_code: Optional[str] = None
    items: List[Item] = Field(default_factory=list)
    attachments: List[Attachment] = Field(default_factory=list)


class FindingRef(BaseModel):
    doc_id: str
    clause: Optional[str] = None
    page: Optional[int] = None
    snippet: Optional[str] = None
    effective_date: Optional[str] = None
    source_path: Optional[str] = None
    image_path: Optional[str] = None


class FindingDetail(BaseModel):
    field: Optional[str] = None
    message: str
    context: Optional[str] = None


class Finding(BaseModel):
    rule_id: str
    message: str
    severity: Literal["error", "warning", "info"]
    ref: FindingRef
    details: List[FindingDetail] = Field(default_factory=list)


class PrecheckResponse(BaseModel):
    status: Literal["ok", "violations"]
    findings: List[Finding]


class DocumentSummary(BaseModel):
    doc_id: str
    title: str
    effective_date: Optional[str] = None
    source_path: Optional[str] = None
    segments: Optional[int] = None
