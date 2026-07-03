from __future__ import annotations

import pandas as pd
import streamlit as st

from storage.database import fetch_admin_items


def render_dashboard(user_id: int) -> None:
    items = fetch_admin_items(user_id)
    if not items:
        st.info("No admin items yet. Import a CSV or run a Gmail scan.")
        return

    df = pd.DataFrame(items)

    needs_review = int((df["status"] == "needs_review").sum()) if "status" in df else 0
    confirmed = int((df["status"] == "confirmed").sum()) if "status" in df else 0
    completed = int((df["status"] == "completed").sum()) if "status" in df else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total items", len(df))
    col2.metric("Needs review", needs_review)
    col3.metric("Confirmed", confirmed)
    col4.metric("Completed", completed)

    st.subheader("Urgency-ranked admin list")
    display_cols = [
        "urgency_score", "status", "admin_type", "source_name", "description",
        "due_date", "amount", "confidence_score"
    ]
    existing = [col for col in display_cols if col in df.columns]
    st.dataframe(df[existing], use_container_width=True, hide_index=True)

    st.subheader("Admin type breakdown")
    if "admin_type" in df.columns:
        counts = df["admin_type"].fillna("unknown").value_counts().reset_index()
        counts.columns = ["admin_type", "count"]
        st.bar_chart(counts, x="admin_type", y="count")
