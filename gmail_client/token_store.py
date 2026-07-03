from __future__ import annotations

from dataclasses import dataclass
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from config import GMAIL_SCOPES, TOKEN_ENCRYPTION_KEY
from storage.database import get_primary_gmail_account, upsert_gmail_account


@dataclass
class StoredCredentials:
    account_id: int
    gmail_address: str
    credentials: Credentials
    token_storage_mode: str


def _get_fernet():
    if not TOKEN_ENCRYPTION_KEY:
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is set but cryptography is not installed. Run: pip install cryptography"
        ) from exc
    return Fernet(TOKEN_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_credentials_json(credentials_json: str) -> tuple[str, str]:
    """Return (stored_value, storage_mode). Plain mode is local-alpha only."""
    fernet = _get_fernet()
    if fernet is None:
        return credentials_json, "plain_local_alpha"
    encrypted = fernet.encrypt(credentials_json.encode("utf-8")).decode("utf-8")
    return encrypted, "fernet"


def decrypt_credentials_json(stored_value: str, storage_mode: str | None) -> str:
    if storage_mode == "fernet":
        fernet = _get_fernet()
        if fernet is None:
            raise RuntimeError("This Gmail token is encrypted but TOKEN_ENCRYPTION_KEY is not set.")
        return fernet.decrypt(stored_value.encode("utf-8")).decode("utf-8")
    return stored_value


def credentials_expiry_iso(creds: Credentials) -> str | None:
    return creds.expiry.isoformat() if getattr(creds, "expiry", None) else None


def save_credentials_for_user(*, user_id: int, gmail_address: str, creds: Credentials) -> int:
    credentials_json = creds.to_json()
    stored_value, storage_mode = encrypt_credentials_json(credentials_json)
    return upsert_gmail_account(
        user_id=user_id,
        gmail_address=gmail_address,
        credentials_json_encrypted=stored_value,
        token_expiry=credentials_expiry_iso(creds),
        token_storage_mode=storage_mode,
    )


def load_credentials_for_user(user_id: int, *, refresh_if_needed: bool = True) -> StoredCredentials | None:
    account = get_primary_gmail_account(user_id)
    if not account or not account.get("credentials_json_encrypted"):
        return None

    credentials_json = decrypt_credentials_json(
        account["credentials_json_encrypted"], account.get("token_storage_mode")
    )
    creds = Credentials.from_authorized_user_info(json.loads(credentials_json), GMAIL_SCOPES)

    if refresh_if_needed and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials_for_user(
            user_id=user_id,
            gmail_address=account["gmail_address"],
            creds=creds,
        )
        account = get_primary_gmail_account(user_id) or account

    return StoredCredentials(
        account_id=int(account["id"]),
        gmail_address=account["gmail_address"],
        credentials=creds,
        token_storage_mode=account.get("token_storage_mode") or "plain_local_alpha",
    )


def token_storage_description() -> str:
    if TOKEN_ENCRYPTION_KEY:
        return "Fernet-encrypted SQLite token storage"
    return "Plain SQLite token storage for local alpha only"
