from __future__ import annotations

import streamlit as st

from storage.database import init_db
from ui.dashboard import render_dashboard
from ui.hosted_gmail import render_hosted_gmail_scan, render_hosted_login_gate
from ui.review_queue import render_review_queue

st.set_page_config(page_title="Admin Scanner Hosted Alpha", layout="wide")
init_db()

try:
    user_id = render_hosted_login_gate()
except Exception as exc:
    st.error(f"Gmail connection failed: {exc}")
    user_id = None

if user_id is None:
    st.stop()

st.title("Admin Scanner Alpha")
st.caption("Hosted Gmail proof: connect in browser, scan Gmail, review extracted admin items.")

tab_gmail, tab_dashboard, tab_review, tab_notes = st.tabs(
    ["Gmail scan", "Dashboard", "Review queue", "Alpha notes"]
)

with tab_gmail:
    render_hosted_gmail_scan(user_id)

with tab_dashboard:
    render_dashboard(user_id)

with tab_review:
    st.header("Review queue")
    render_review_queue(user_id)

with tab_notes:
    st.header("Hosted alpha notes")
    st.markdown(
        """
        **This build answers the key bottleneck:** can another person open a hosted link, grant Gmail read-only access in the browser,
        and run a scan?

        **Still alpha-only:**
        - Use Google OAuth testing mode with named test users.
        - Use a very small tester group.
        - Do not treat this as production or as a public launch.
        - Streamlit Community Cloud storage is not a durable production database.
        - The next production step would be a proper backend, hosted database, encrypted token store, deletion flow and Google verification prep.
        """
    )
