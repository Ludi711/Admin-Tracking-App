from __future__ import annotations

import streamlit as st

from extraction.import_csv import import_admin_csv
from storage.database import init_db
from ui.dashboard import render_dashboard
from ui.review_queue import render_review_queue
from ui.settings import render_user_selector

st.set_page_config(page_title="Admin Scanner Alpha", layout="wide")
init_db()

st.title("Admin Scanner Alpha")
st.caption("Tiny alpha: import or scan emails, extract admin items, review, and rank by urgency.")

user_id = render_user_selector()

if user_id is None:
    st.warning("Create an alpha user in the sidebar to begin.")
    st.stop()

tab_dashboard, tab_import, tab_review, tab_gmail, tab_notes = st.tabs(
    ["Dashboard", "Import CSV", "Review queue", "Gmail scan", "Alpha notes"]
)

with tab_dashboard:
    render_dashboard(user_id)

with tab_import:
    st.header("Import scanner output")
    st.write(
        "Upload your existing scanner CSV first. This lets you test the multi-user dashboard and review queue before dealing with Gmail OAuth."
    )
    uploaded = st.file_uploader("CSV file", type=["csv"])
    if uploaded is not None:
        if st.button("Import CSV"):
            result = import_admin_csv(user_id, uploaded)
            st.success(
                f"Imported {result['imported']} admin items from {result['rows']} rows. Skipped {result['skipped']} rows."
            )

with tab_review:
    st.header("Review queue")
    render_review_queue(user_id)

with tab_gmail:
    st.header("Gmail scan")
    st.info(
        "Gmail OAuth is intentionally left as a wiring step. Get the CSV/import/review flow working first, then connect your existing scanner here."
    )
    st.code(
        """# Intended next wiring step:
from gmail_client.oauth import run_local_oauth_flow
from gmail_client.client import build_gmail_service
from gmail_client.sync import sync_gmail_query

creds = run_local_oauth_flow()
service = build_gmail_service(creds)
result = sync_gmail_query(service, user_id, query='newer_than:6m', max_results=100)
""",
        language="python",
    )

with tab_notes:
    st.header("Alpha definition")
    st.markdown(
        """
        **Alpha goal:** a second person can import or connect email data, get a useful urgency-ranked admin list, and review/correct items without code changes.

        **Keep for alpha:**
        - what it is
        - relevant date
        - relevant amount
        - source/company
        - confidence
        - review status

        **Avoid for alpha:**
        - storing full email bodies
        - background sync
        - payments
        - mobile app
        - complex account management
        """
    )
