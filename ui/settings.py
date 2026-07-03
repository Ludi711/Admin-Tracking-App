from __future__ import annotations

import streamlit as st

from storage.database import get_or_create_user, list_users


def render_user_selector() -> int | None:
    st.sidebar.header("Alpha user")
    users = list_users()
    options = {f"{u.get('display_name') or u['email']} ({u['email']})": u["id"] for u in users}

    if options:
        selected = st.sidebar.selectbox("Current user", list(options.keys()))
        current_user_id = options[selected]
    else:
        current_user_id = None
        st.sidebar.info("Create your first alpha user.")

    with st.sidebar.expander("Add alpha user"):
        email = st.text_input("Email")
        display_name = st.text_input("Display name")
        if st.button("Create user"):
            if email.strip():
                user_id = get_or_create_user(email, display_name or None)
                st.success("User created")
                st.rerun()
            else:
                st.warning("Enter an email address.")

    return current_user_id
