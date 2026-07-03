from __future__ import annotations

import hashlib
from typing import Iterable

import pandas as pd

from extraction.extractor import extract_admin_item, as_dict
from storage.database import insert_admin_item, insert_email_source


def _first_present(row: pd.Series, candidates: Iterable[str]) -> str | None:
    lower_map = {str(col).lower().strip(): col for col in row.index}
    for candidate in candidates:
        col = lower_map.get(candidate.lower())
        if col is not None:
            value = row.get(col)
            if pd.notna(value) and str(value).strip():
                return str(value).strip()
    return None


def _stable_message_id(row: pd.Series) -> str:
    raw = "|".join(str(row.get(col, "")) for col in row.index)
    return "csv_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def import_admin_csv(user_id: int, csv_file) -> dict:
    df = pd.read_csv(csv_file)
    imported = 0
    skipped = 0

    for _, row in df.iterrows():
        sender = _first_present(row, ["sender", "from", "from_email", "email_from"])
        subject = _first_present(row, ["subject", "email_subject", "title"])
        received_at = _first_present(row, ["date", "received_at", "date_received", "timestamp"])
        snippet = _first_present(row, ["snippet", "preview", "summary"])
        body = _first_present(row, ["body", "email_body", "text", "content"])
        gmail_message_id = _first_present(row, ["gmail_message_id", "message_id", "id"]) or _stable_message_id(row)
        thread_id = _first_present(row, ["thread_id", "gmail_thread_id"])

        existing_fields = {
            "source_name": _first_present(row, ["source_name", "company", "supplier"]),
            "admin_type": _first_present(row, ["admin_type", "category", "type"]),
            "description": _first_present(row, ["description", "admin_description", "task"]),
            "due_date": _first_present(row, ["due_date", "deadline", "relevant_date"]),
            "amount": _first_present(row, ["amount", "relevant_amount"]),
            "urgency_score": _first_present(row, ["urgency_score", "priority_score"]),
            "confidence_score": _first_present(row, ["confidence_score", "confidence"]),
            "status": _first_present(row, ["status"]),
        }

        extracted = extract_admin_item(
            sender=sender,
            subject=subject,
            snippet=snippet,
            body=body,
            existing_fields=existing_fields,
        )

        if extracted is None:
            skipped += 1
            continue

        email_source_id = insert_email_source(
            user_id=user_id,
            gmail_message_id=gmail_message_id,
            thread_id=thread_id,
            sender=sender,
            subject=subject,
            received_at=received_at,
            snippet=snippet,
            source_type="csv_import",
        )

        item = as_dict(extracted)
        item.update(
            {
                "user_id": user_id,
                "email_source_id": email_source_id,
                "gmail_message_id": gmail_message_id,
                "subject": subject,
            }
        )
        insert_admin_item(item)
        imported += 1

    return {"imported": imported, "skipped": skipped, "rows": len(df)}
