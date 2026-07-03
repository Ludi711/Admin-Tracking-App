from __future__ import annotations

import streamlit as st

from storage.database import fetch_admin_items, update_admin_item_fields, update_admin_item_status

STATUSES = ["needs_review", "confirmed", "ignored", "incorrect", "completed"]


def render_review_queue(user_id: int) -> None:
    status_filter = st.selectbox("Filter by status", ["needs_review", "confirmed", "ignored", "incorrect", "completed", "all"])
    items = fetch_admin_items(user_id, None if status_filter == "all" else status_filter)

    if not items:
        st.info("No items in this queue.")
        return

    for item in items:
        with st.expander(f"{item.get('admin_type') or 'admin'} — {item.get('description') or item.get('subject')}"):
            st.caption(f"Source: {item.get('source_name') or 'Unknown'} | Confidence: {item.get('confidence_score')} | Urgency: {item.get('urgency_score')}")

            col1, col2 = st.columns(2)
            new_admin_type = col1.text_input("Admin type", value=item.get("admin_type") or "", key=f"type_{item['id']}")
            new_source = col2.text_input("Source", value=item.get("source_name") or "", key=f"source_{item['id']}")

            new_description = st.text_area("Description", value=item.get("description") or "", key=f"desc_{item['id']}")

            col3, col4, col5 = st.columns(3)
            new_due_date = col3.text_input("Due date", value=item.get("due_date") or "", key=f"due_{item['id']}")
            new_amount = col4.text_input("Amount", value="" if item.get("amount") is None else str(item.get("amount")), key=f"amount_{item['id']}")
            new_status = col5.selectbox("Status", STATUSES, index=STATUSES.index(item.get("status") or "needs_review"), key=f"status_{item['id']}")

            notes = st.text_area("Review notes", value=item.get("review_notes") or "", key=f"notes_{item['id']}")

            save_col, confirm_col, ignore_col, done_col = st.columns(4)
            if save_col.button("Save edits", key=f"save_{item['id']}"):
                update_admin_item_fields(
                    item["id"],
                    {
                        "admin_type": new_admin_type,
                        "source_name": new_source,
                        "description": new_description,
                        "due_date": new_due_date or None,
                        "amount": _safe_float(new_amount),
                        "status": new_status,
                        "review_notes": notes,
                    },
                )
                st.success("Saved")
                st.rerun()

            if confirm_col.button("Confirm", key=f"confirm_{item['id']}"):
                update_admin_item_status(item["id"], "confirmed", notes)
                st.rerun()
            if ignore_col.button("Ignore", key=f"ignore_{item['id']}"):
                update_admin_item_status(item["id"], "ignored", notes)
                st.rerun()
            if done_col.button("Complete", key=f"complete_{item['id']}"):
                update_admin_item_status(item["id"], "completed", notes)
                st.rerun()


def _safe_float(value: str | None):
    if not value:
        return None
    try:
        return float(str(value).replace("£", "").replace(",", ""))
    except ValueError:
        return None
