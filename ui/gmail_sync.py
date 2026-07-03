from __future__ import annotations

import streamlit as st

from config import GOOGLE_CLIENT_SECRETS_FILE, TOKEN_ENCRYPTION_KEY
from gmail_client.client import build_gmail_service
from gmail_client.oauth import client_secrets_file_exists, connect_gmail_for_user
from gmail_client.sync import build_admin_search_query, sync_gmail_query
from gmail_client.token_store import load_credentials_for_user, token_storage_description
from storage.database import delete_gmail_account, list_gmail_accounts


def render_gmail_sync(user_id: int) -> None:
    st.header("Gmail sync")
    st.write(
        "Connect a Gmail account using read-only OAuth, scan recent emails, and send extracted admin items into the same dashboard/review queue."
    )

    with st.expander("Setup checklist", expanded=not client_secrets_file_exists()):
        st.markdown(
            f"""
            1. Create a Google Cloud project.
            2. Enable the Gmail API.
            3. Create an OAuth **Desktop app** client for this local alpha.
            4. Download the client JSON and save it here:

            ```text
            {GOOGLE_CLIENT_SECRETS_FILE}
            ```

            5. Add your own Gmail and any trusted testers as OAuth test users in Google Cloud.
            """
        )
        st.caption(f"Token storage mode: {token_storage_description()}")
        if not TOKEN_ENCRYPTION_KEY:
            st.warning(
                "No TOKEN_ENCRYPTION_KEY is set, so tokens are stored in plain text in SQLite. This is okay only for a local/private alpha."
            )

    if not client_secrets_file_exists():
        st.error("client_secret.json is missing. Add Google OAuth credentials before connecting Gmail.")
        return

    accounts = list_gmail_accounts(user_id)
    if accounts:
        st.subheader("Connected Gmail account")
        account = accounts[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Gmail", account.get("gmail_address") or "Unknown")
        col2.metric("Last sync", account.get("last_sync_at") or "Never")
        col3.metric("Token", account.get("token_storage_mode") or "Unknown")

        with st.expander("Disconnect Gmail"):
            st.warning("This removes the saved OAuth token from the local alpha database. It does not delete extracted admin items.")
            if st.button("Remove saved Gmail connection"):
                delete_gmail_account(int(account["id"]), user_id)
                st.success("Gmail connection removed.")
                st.rerun()
    else:
        st.info("No Gmail account connected for this alpha user yet.")

    if st.button("Connect / reconnect Gmail"):
        try:
            result = connect_gmail_for_user(user_id)
            st.success(f"Connected Gmail account: {result['gmail_address']}")
            st.rerun()
        except Exception as exc:
            st.error(f"Gmail connection failed: {exc}")
            return

    st.divider()
    st.subheader("Run a manual scan")

    stored = load_credentials_for_user(user_id, refresh_if_needed=True)
    if stored is None:
        st.info("Connect Gmail first, then run a scan.")
        return

    col1, col2 = st.columns(2)
    days = col1.selectbox("Scan period", [30, 90, 180, 365], index=2, format_func=lambda d: f"Last {d} days")
    max_results = col2.slider("Max Gmail messages to inspect", min_value=25, max_value=500, value=100, step=25)

    query_mode = st.radio(
        "Search mode",
        ["Targeted admin keywords", "Broad date scan", "Custom Gmail query"],
        horizontal=True,
    )

    if query_mode == "Targeted admin keywords":
        query = build_admin_search_query(days=days, targeted=True)
    elif query_mode == "Broad date scan":
        query = build_admin_search_query(days=days, targeted=False)
    else:
        query = st.text_input("Custom Gmail query", value=build_admin_search_query(days=days, targeted=True))

    st.caption("Gmail query to run:")
    st.code(query, language="text")

    if st.button("Scan Gmail now", type="primary"):
        try:
            service = build_gmail_service(stored.credentials)
            with st.spinner("Scanning Gmail and extracting admin items..."):
                result = sync_gmail_query(
                    service,
                    user_id=user_id,
                    query=query,
                    max_results=max_results,
                    account_id=stored.account_id,
                )
            st.success(
                f"Scan complete: imported {result['imported']} admin items from {result['matched_messages']} matched messages."
            )
            st.write(
                {
                    "skipped_non_admin": result["skipped_non_admin"],
                    "skipped_duplicate": result["skipped_duplicate"],
                    "errors": len(result["errors"]),
                }
            )
            if result["errors"]:
                with st.expander("Scan errors"):
                    for error in result["errors"][:20]:
                        st.write(error)
            st.info("Open the Dashboard or Review Queue tab to inspect the extracted items.")
        except Exception as exc:
            st.error(f"Gmail scan failed: {exc}")
