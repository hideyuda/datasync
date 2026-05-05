import json
import os
from typing import Optional, Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
]


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_chat_client():
    client_id = env("GCHAT_CLIENT_ID")
    client_secret = env("GCHAT_CLIENT_SECRET")
    refresh_token = env("GCHAT_REFRESH_TOKEN")

    if not (client_id and client_secret and refresh_token):
        print("GChat: missing secrets, skipping.")
        return None

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    return build("chat", "v1", credentials=creds, cache_discovery=False)


def sync() -> None:
    service = build_chat_client()
    if service is None:
        return

    print("GChat: Fetching spaces...")
    spaces = []
    page_token = None
    while True:
        resp = service.spaces().list(pageToken=page_token).execute()
        spaces.extend(resp.get("spaces", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"GChat: Found {len(spaces)} spaces.")

    ensure_dir(os.path.join("data", "spaces"))

    for space in spaces:
        space_name = space.get("name")  # e.g. spaces/AAAA...
        if not space_name:
            continue

        space_id = space_name.split("/")[-1]
        display_name = space.get("displayName", "Untitled")
        safe_name = "".join(
            [c for c in display_name if c.isalnum() or c in (" ", "-", "_")]
        ).strip()
        if not safe_name:
            safe_name = space_id

        print(f"GChat: Syncing space {display_name} ({space_id})...")

        # Save space info
        save_json(os.path.join("data", "spaces", f"{safe_name}_{space_id}.json"), space)

        # List messages
        messages = []
        msg_page_token = None
        # Limit to recent messages or fetch all? Let's fetch a reasonable amount or all if possible.
        # Note: Listing messages might take a while for large spaces.
        # For now, let's just fetch the first page or so to verify it works, or loop until done.
        # To avoid hitting limits or taking too long, maybe we can limit or just do it.
        # Let's try to fetch all but be mindful.

        try:
            while True:
                # filter=None fetches all messages? Or do we need to specify something?
                # The API documentation says 'parent' is required.
                msg_resp = (
                    service.spaces()
                    .messages()
                    .list(
                        parent=space_name,
                        pageToken=msg_page_token,
                        pageSize=1000,  # Max is 1000
                    )
                    .execute()
                )

                msgs = msg_resp.get("messages", [])
                messages.extend(msgs)

                msg_page_token = msg_resp.get("nextPageToken")
                if not msg_page_token:
                    break
        except Exception as e:
            print(f"GChat: Error fetching messages for {space_name}: {e}")

        # Save messages
        if messages:
            messages_dir = os.path.join("data", "messages", f"{safe_name}_{space_id}")
            ensure_dir(messages_dir)

            # Save as one big JSON or split? One big JSON for now.
            save_json(os.path.join(messages_dir, "messages.json"), messages)

            # Create a markdown summary
            md_path = os.path.join(messages_dir, "messages.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"# {display_name}\n\n")
                for msg in reversed(messages):  # Oldest first
                    sender = msg.get("sender", {}).get("displayName", "Unknown")
                    create_time = msg.get("createTime")
                    text = msg.get("text", "")
                    f.write(f"**{sender}** ({create_time}):\n{text}\n\n")

    print("GChat: Sync complete.")


if __name__ == "__main__":
    sync()
