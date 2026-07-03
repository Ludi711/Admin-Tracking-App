from __future__ import annotations

from extraction.extractor import extract_admin_item, as_dict
from gmail_client.client import fetch_message, search_message_ids
from storage.database import insert_admin_item, insert_email_source


def sync_gmail_query(service, user_id: int, query: str, max_results: int = 50) -> dict:
    """Fetch Gmail messages matching a query and store extracted admin items."""
    message_ids = search_message_ids(service, query=query, max_results=max_results)
    imported = 0
    skipped = 0

    for message_id in message_ids:
        email = fetch_message(service, message_id)
        extracted = extract_admin_item(
            sender=email.get("sender"),
            subject=email.get("subject"),
            snippet=email.get("snippet"),
            body=email.get("body"),
        )
        if extracted is None:
            skipped += 1
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

    return {"matched_messages": len(message_ids), "imported": imported, "skipped": skipped}
