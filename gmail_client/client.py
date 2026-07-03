from __future__ import annotations

import base64
from email.utils import parsedate_to_datetime
from typing import Any

from googleapiclient.discovery import build


def build_gmail_service(credentials):
    return build("gmail", "v1", credentials=credentials)


def search_message_ids(service, query: str, max_results: int = 50) -> list[str]:
    response = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results,
    ).execute()
    return [message["id"] for message in response.get("messages", [])]


def _header(headers: list[dict[str, str]], name: str) -> str | None:
    for item in headers:
        if item.get("name", "").lower() == name.lower():
            return item.get("value")
    return None


def _decode_body(payload: dict[str, Any]) -> str | None:
    data = payload.get("body", {}).get("data")
    if data:
        try:
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")
        except Exception:
            return None

    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain":
            body = _decode_body(part)
            if body:
                return body
    return None


def fetch_message(service, message_id: str) -> dict:
    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    received_raw = _header(headers, "Date")
    received_at = None
    if received_raw:
        try:
            received_at = parsedate_to_datetime(received_raw).isoformat()
        except Exception:
            received_at = received_raw

    return {
        "gmail_message_id": message.get("id"),
        "thread_id": message.get("threadId"),
        "sender": _header(headers, "From"),
        "subject": _header(headers, "Subject"),
        "received_at": received_at,
        "snippet": message.get("snippet"),
        "body": _decode_body(payload),
    }
