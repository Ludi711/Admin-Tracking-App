from __future__ import annotations

from extraction.extractor import extract_admin_item, as_dict
from gmail_client.client import fetch_message, search_message_ids
from storage.database import (
    admin_item_exists_for_message,
    insert_admin_item,
    insert_email_source,
    update_gmail_last_sync,
)

ADMIN_SEARCH_TERMS = [
    "renewal",
    "renews",
    "expires",
    "bill",
    "invoice",
    "statement",
    "payment due",
    "direct debit",
    "subscription",
    "insurance",
    "policy",
    "appointment",
    "booking",
    "reservation",
    "hmrc",
    "tax",
    "council tax",
    "parking charge",
    "penalty notice",
    "utility",
]


def build_admin_search_query(days: int = 180, *, targeted: bool = True) -> str:
    days = max(1, int(days))
    base = f"newer_than:{days}d"

    if not targeted:
        return base

    terms = " OR ".join(
        f'"{term}"' if " " in term else term
        for term in ADMIN_SEARCH_TERMS
    )

    return f"{base} ({terms})"


def sync_gmail_query(
    service,
    user_id: int,
    query: str,
    max_results: int = 50,
    *,
    account_id: int | None = None,
) -> dict:
    """Fetch Gmail messages matching a query and store extracted admin items.

    Raw email bodies are fetched only in memory for extraction and are not stored.
    """
    message_ids = search_message_ids(
        service,
        query=query,
        max_results=max_results,
    )

    imported = 0
    skipped_non_admin = 0
    skipped_duplicate = 0
    errors: list[str] = []

    for message_id in message_ids:
        if admin_item_exists_for_message(user_id, message_id):
            skipped_duplicate += 1
            continue

        try:
            email = fetch_message(
                service,
                message_id,
                include_body=True,
            )

            extracted = extract_admin_item(
                sender=email.get("sender"),
                subject=email.get("subject"),
                snippet=email.get("snippet"),
                body=email.get("body"),
            )

            # Do not store raw body after extraction.
            email.pop("body", None)

            if extracted is None:
                skipped_non_admin += 1
                continue

            email_source_id = insert_email_source(
                user_id=user_id,
                gmail_message_id=email.get("gmail_message_id"),
                thread_id=email.get("thread_id"),
                sender=email.get("sender"),
                subject=email.get("subject"),
                received_at=email.get("received_at"),
                snippet=email.get("snippet"),
                source_type="gmail_oauth",
            )

            item = as_dict(extracted)
            item.update(
                {
                    "user_id": user_id,
                    "email_source_id": email_source_id,
                    "gmail_message_id": email.get("gmail_message_id"),
                    "subject": email.get("subject"),
                }
            )

            insert_admin_item(item)
            imported += 1

        except Exception as exc:
            errors.append(f"{message_id}: {exc}")

    if account_id is not None:
        update_gmail_last_sync(account_id)

    return {
        "matched_messages": len(message_ids),
        "imported": imported,
        "skipped_non_admin": skipped_non_admin,
        "skipped_duplicate": skipped_duplicate,
        "errors": errors,
        "query": query,
    }
