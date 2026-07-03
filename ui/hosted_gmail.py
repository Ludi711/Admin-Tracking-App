from __future__ import annotations

from urllib.parse import unquote

import streamlit as st

from gmail_client.client import build_gmail_service, get_gmail_profile
from gmail_client.sync import build_admin_search_query, sync_gmail_query
from gmail_client.token_store import load_credentials_for_user, save_credentials_for_user
from gmail_client.web_oauth import (
    build_authorization_url,
    exchange_code_for_credentials,
    hosted_oauth_configured,
)
from storage.database import get_or_create_user, list_gmail_accounts


def _get_query_param(name: str) -> str | None:
    value = st.query_params.get(name)
    if isinstance(value, list):
        value = value[0] if value else None
    return unquote(value) if value else None


def handle_hosted_oauth_callback() -> int | None:
    """Handle Google redirect back to the hosted Streamlit app.

    Returns the connected/created user_id, or None when no callback is present.
    """
    code = _get_query_param("code")
    state = _get_query_param("state")
    error = _get_query_param("error")

    if error:
        st.error(f"Google OAuth returned an error: {error}")
        st.query_params.clear()
        return None

    if not code and not state:
        return None

    if not code or not state:
        st.error("OAuth callback was missing a code or state. Please try connecting again.")
        st.query_params.clear()
        return None

    try:
        with st.spinner("Finishing Gmail connection..."):
            creds = exchange_code_for_credentials(code=code, state=state)
            service = build_gmail_service(creds)
            profile = get_gmail_profile(service)
            gmail_address = profile.get("emailAddress")
            if not gmail_address:
                raise RuntimeError("Could not determine the connected Gmail address.")

            user_id = get_or_create_user(email=gmail_address, display_name=gmail_address)
            save_credentials_for_user(user_id=user_id, gmail_address=gmail_address, creds=creds)

        st.session_state["hosted_user_id"] = user_id
        st.session_state["hosted_gmail_address"] = gmail_address
        st.query_params.clear()
        st.success(f"Connected Gmail: {gmail_address}")
        return user_id
    except Exception as exc:
        st.query_params.clear()
        st.error(f"Gmail connection failed: {exc}")
        st.info("Please click Connect Gmail again to start a fresh Google sign-in. Old callback codes can only be used once.")
        return None


def render_hosted_login_gate() -> int | None:
    """Show a simple hosted-web login/connect page and return user_id when connected."""
    if st.session_state.get("hosted_user_id"):
        return int(st.session_state["hosted_user_id"])

    callback_user_id = handle_hosted_oauth_callback()
    if callback_user_id:
        return callback_user_id

    st.title("Admin Scanner Alpha")
    st.caption("Hosted proof: click a web link, connect Gmail in the browser, then run a scan.")

    st.markdown(
        """
        This alpha asks for **read-only Gmail access** so it can scan recent emails for bills, renewals, subscriptions,
        appointments, tax/admin messages and deadlines.

        For this proof, raw email bodies are used in memory during extraction and are not stored in the SQLite database.
        """
    )

    if not hosted_oauth_configured():
        st.error(
            "Hosted OAuth is not configured yet. Add GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI to Streamlit secrets."
        )
        return None

    auth_url = build_authorization_url()
    st.link_button("Connect Gmail", auth_url, type="primary")

    with st.expander("What this alpha can and cannot do"):
        st.markdown(
            """
            **Can do:**
            - Open a Google consent screen from a hosted web link
            - Request read-only Gmail access
            - Fetch matching Gmail messages
            - Extract structured admin items
            - Show a review queue and urgency dashboard

            **Cannot do yet:**
            - Production-grade account management
            - Payment/signup flows
            - Long-term hosted database storage
            - Google verification/security assessment
            - Background sync
            """
        )

    return None


def render_hosted_gmail_scan(user_id: int) -> None:
    st.header("Gmail scan")

    stored = load_credentials_for_user(user_id, refresh_if_needed=True)
    if stored is None:
        st.warning("No saved Gmail credentials found. Reconnect Gmail from the landing page.")
        if st.button("Reset connection"):
            st.session_state.pop("hosted_user_id", None)
            st.session_state.pop("hosted_gmail_address", None)
            st.rerun()
        return

    accounts = list_gmail_accounts(user_id)
    account = accounts[0] if accounts else {}
    col1, col2, col3 = st.columns(3)
    col1.metric("Connected Gmail", stored.gmail_address)
    col2.metric("Last sync", account.get("last_sync_at") or "Never")
    col3.metric("Token mode", stored.token_storage_mode)

    col1, col2 = st.columns(2)
    days = col1.selectbox("Scan period", [30, 90, 180, 365], index=1, format_func=lambda d: f"Last {d} days")
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

    st.divider()
    if st.button("Disconnect this browser session"):
        st.session_state.pop("hosted_user_id", None)
        st.session_state.pop("hosted_gmail_address", None)
        st.rerun()
