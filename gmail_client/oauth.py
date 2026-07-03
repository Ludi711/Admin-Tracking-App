from __future__ import annotations

"""Gmail OAuth placeholder for the alpha.

For the first alpha, do not make Gmail OAuth the bottleneck. Use CSV import first,
then wire this module once the core dashboard/review flow works.

This file shows the intended shape, but token persistence/encryption should be
hardened before inviting real users beyond close testers.
"""

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from config import GMAIL_SCOPES, GOOGLE_CLIENT_SECRETS_FILE


def run_local_oauth_flow(client_secret_file: str | Path = GOOGLE_CLIENT_SECRETS_FILE):
    """Run a local OAuth flow and return Google credentials.

    This is suitable for local developer testing only.
    Production should use a server-side OAuth callback and encrypted token storage.
    """
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes=GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)
    return creds
