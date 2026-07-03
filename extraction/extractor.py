from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Optional

from dateutil import parser as date_parser


@dataclass
class ExtractedAdminItem:
    source_name: str | None
    admin_type: str
    description: str
    due_date: str | None
    amount: float | None
    urgency_score: int
    confidence_score: float
    status: str = "needs_review"


ADMIN_KEYWORDS = {
    "insurance": ["insurance", "policy", "renewal", "cover"],
    "utility_bill": ["bill", "statement", "energy", "electricity", "gas", "water", "broadband"],
    "subscription": ["subscription", "membership", "renew", "trial", "plan"],
    "appointment": ["appointment", "booking", "reservation", "confirmed", "reminder"],
    "tax_admin": ["hmrc", "tax", "self assessment", "payment on account"],
    "fine_or_penalty": ["penalty", "fine", "parking charge", "notice"],
    "banking_admin": ["card", "bank", "statement", "direct debit", "payment due"],
    "travel": ["flight", "hotel", "train", "itinerary", "boarding", "booking reference"],
}

MONEY_RE = re.compile(r"(?:£|GBP\s?)(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)", re.IGNORECASE)
DATE_HINT_RE = re.compile(
    r"(?:due|expires|renew(?:s|al)?|appointment|booking|by|before|on)\s+(?:date\s+)?(?:is\s+)?([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def _normalise_text(*parts: str | None) -> str:
    return " ".join([p for p in parts if p]).strip()


def _guess_admin_type(text: str) -> tuple[str, float]:
    lower = text.lower()
    scores: dict[str, int] = {}
    for admin_type, words in ADMIN_KEYWORDS.items():
        scores[admin_type] = sum(1 for word in words if word in lower)
    best_type, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score == 0:
        return "unknown_admin", 0.35
    confidence = min(0.95, 0.45 + best_score * 0.15)
    return best_type, confidence


def _extract_amount(text: str) -> Optional[float]:
    match = MONEY_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _extract_due_date(text: str) -> Optional[str]:
    match = DATE_HINT_RE.search(text)
    if not match:
        return None
    raw_date = match.group(1)
    try:
        parsed = date_parser.parse(raw_date, dayfirst=True, fuzzy=True)
        return parsed.date().isoformat()
    except Exception:
        return None


def _urgency_score(due_date: str | None, confidence: float) -> int:
    if not due_date:
        return int(35 + confidence * 20)
    try:
        due = datetime.fromisoformat(due_date).date()
    except ValueError:
        return 50
    days = (due - date.today()).days
    if days < 0:
        return 100
    if days <= 7:
        return 95
    if days <= 30:
        return 80
    if days <= 90:
        return 60
    return 40


def extract_admin_item(
    *,
    sender: str | None,
    subject: str | None,
    snippet: str | None = None,
    body: str | None = None,
    existing_fields: dict | None = None,
) -> ExtractedAdminItem | None:
    """Basic extraction fallback.

    Replace or augment this with your current V3 extraction logic.
    Return None when the email does not look like admin.
    """
    existing_fields = existing_fields or {}

    if existing_fields.get("admin_type") or existing_fields.get("description"):
        return ExtractedAdminItem(
            source_name=existing_fields.get("source_name") or sender,
            admin_type=existing_fields.get("admin_type") or "unknown_admin",
            description=existing_fields.get("description") or subject or "Admin item",
            due_date=existing_fields.get("due_date"),
            amount=_safe_float(existing_fields.get("amount")),
            urgency_score=int(existing_fields.get("urgency_score") or 50),
            confidence_score=float(existing_fields.get("confidence_score") or 0.65),
            status=existing_fields.get("status") or "needs_review",
        )

    text = _normalise_text(subject, snippet, body)
    if not text:
        return None

    admin_type, confidence = _guess_admin_type(text)
    if admin_type == "unknown_admin" and confidence < 0.4:
        return None

    amount = _extract_amount(text)
    due_date = _extract_due_date(text)
    urgency = _urgency_score(due_date, confidence)
    description = subject or snippet or "Admin item"

    return ExtractedAdminItem(
        source_name=sender,
        admin_type=admin_type,
        description=description[:240],
        due_date=due_date,
        amount=amount,
        urgency_score=urgency,
        confidence_score=confidence,
    )


def _safe_float(value) -> float | None:
    if value in (None, "", "nan"):
        return None
    try:
        return float(str(value).replace("£", "").replace(",", ""))
    except ValueError:
        return None


def as_dict(item: ExtractedAdminItem) -> dict:
    return asdict(item)
