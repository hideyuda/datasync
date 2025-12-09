import base64
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def build_gmail_client() -> Optional[any]:
    client_id = env("GMAIL_CLIENT_ID")
    client_secret = env("GMAIL_CLIENT_SECRET")
    refresh_token = env("GMAIL_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        print("Gmail: missing secrets, skipping.")
        return None

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
        ],
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def load_state(state_path: str) -> Dict:
    if os.path.exists(state_path):
        with open(state_path, "r") as f:
            return json.load(f)
    return {}


def save_state(state_path: str, state: Dict) -> None:
    ensure_dir(os.path.dirname(state_path))
    with open(state_path, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def save_message_eml(message_id: str, raw_b64url: str) -> None:
    ensure_dir("data/eml")
    eml_path = os.path.join("data", "eml", f"{message_id}.eml")
    raw_bytes = base64.urlsafe_b64decode(raw_b64url.encode("utf-8"))
    with open(eml_path, "wb") as f:
        f.write(raw_bytes)


def save_message_index(message_id: str, meta: Dict) -> None:
    ensure_dir("data/index")
    idx_path = os.path.join("data", "index", f"{message_id}.json")
    with open(idx_path, "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def choose_query(state: Dict) -> str:
    # Prefer user-provided query; otherwise incremental; otherwise safe default.
    user_query = env("GMAIL_QUERY")
    if user_query:
        return user_query
    if env("GMAIL_FULL_SYNC", "false").lower() == "true":
        return ""  # full
    # default: last 90 days
    return "newer_than:90d"


def fetch_all_message_ids(gmail, user_id: str, query: str) -> List[str]:
    ids: List[str] = []
    next_page_token = None
    while True:
        try:
            req = (
                gmail.users()
                .messages()
                .list(
                    userId=user_id,
                    q=query,
                    pageToken=next_page_token,
                    maxResults=500,
                )
            )
            resp = req.execute()
        except HttpError as e:
            print(f"Error listing messages: {e}")
            break

        for m in resp.get("messages", []):
            ids.append(m["id"])

        next_page_token = resp.get("nextPageToken")
        if not next_page_token:
            break
        # be polite
        time.sleep(0.1)
    return ids


def sync() -> None:
    gmail = build_gmail_client()
    if gmail is None:
        return

    user_email = env("GMAIL_USER_EMAIL", "me")
    state_path = os.path.join("data", "state.json")
    state = load_state(state_path)

    query = choose_query(state)
    print(f"Gmail query: '{query or '(full)'}'")

    message_ids = fetch_all_message_ids(gmail, user_email, query)
    print(f"Found {len(message_ids)} messages")

    fetched = 0
    for mid in message_ids:
        eml_path = os.path.join("data", "eml", f"{mid}.eml")
        if os.path.exists(eml_path):
            continue
        try:
            m = (
                gmail.users()
                .messages()
                .get(
                    userId=user_email,
                    id=mid,
                    format="raw",
                )
                .execute()
            )

            save_message_eml(mid, m["raw"])

            # also fetch minimal metadata for index
            meta = (
                gmail.users()
                .messages()
                .get(
                    userId=user_email,
                    id=mid,
                    format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Date"],
                )
                .execute()
            )
            save_message_index(mid, meta)
            fetched += 1
        except HttpError as e:
            print(f"Error fetching {mid}: {e}")
        # throttle a bit to reduce API pressure
        time.sleep(0.05)

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state_path, state)
    print(f"Fetched {fetched} new messages")


if __name__ == "__main__":
    sync()
