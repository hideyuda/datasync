import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests


API_BASE = "https://api.chatwork.com/v2"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def load_state() -> Dict[str, Any]:
    path = os.path.join("data", "state.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: Dict[str, Any]) -> None:
    ensure_dir("data")
    with open(os.path.join("data", "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def safe_filename(name: str, fallback: str) -> str:
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    return safe_name or fallback


class ChatworkClient:
    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update({"X-ChatWorkToken": token})

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        resp = self.session.get(f"{API_BASE}{path}", params=params, timeout=30)
        if resp.status_code == 204:
            return []
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            print(f"Chatwork: rate limited, sleeping {retry_after}s...")
            time.sleep(retry_after)
            resp = self.session.get(f"{API_BASE}{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def list_rooms(self) -> List[Dict[str, Any]]:
        return self.get("/rooms")

    def list_messages(self, room_id: int) -> List[Dict[str, Any]]:
        return self.get(f"/rooms/{room_id}/messages", params={"force": 1})


def write_jsonl(room_dir: str, message: Dict[str, Any]) -> None:
    send_time = int(message.get("send_time") or 0)
    dt = datetime.fromtimestamp(send_time, tz=timezone.utc)
    path = os.path.join(room_dir, dt.strftime("%Y-%m-%d") + ".jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


def parse_room_filter() -> Optional[set[int]]:
    raw = env("CHATWORK_ROOM_IDS")
    if not raw:
        return None
    room_ids = set()
    for item in raw.split(","):
        item = item.strip()
        if item:
            room_ids.add(int(item))
    return room_ids


def sync() -> None:
    token = env("CHATWORK_API_TOKEN")
    if not token:
        print("Chatwork: CHATWORK_API_TOKEN not found, skipping.")
        return

    client = ChatworkClient(token)
    state = load_state()
    room_state = state.setdefault("rooms", {})
    room_filter = parse_room_filter()

    print("Chatwork: Fetching rooms...")
    rooms = client.list_rooms()
    if room_filter is not None:
        rooms = [room for room in rooms if int(room["room_id"]) in room_filter]
    print(f"Chatwork: Found {len(rooms)} rooms.")

    ensure_dir(os.path.join("data", "rooms"))

    for room in rooms:
        room_id = int(room["room_id"])
        room_name = room.get("name") or str(room_id)
        room_key = str(room_id)
        room_slug = f"{safe_filename(room_name, room_key)}_{room_id}"

        save_json(os.path.join("data", "rooms", f"{room_slug}.json"), room)

        last_message_id = int(room_state.get(room_key, {}).get("last_message_id") or 0)
        try:
            messages = client.list_messages(room_id)
        except requests.HTTPError as e:
            print(f"Chatwork: Error fetching messages for {room_name} ({room_id}): {e}")
            continue

        new_messages = [
            msg
            for msg in messages
            if int(msg.get("message_id") or 0) > last_message_id
        ]
        new_messages.sort(key=lambda msg: int(msg.get("message_id") or 0))

        room_dir = os.path.join("data", "chatwork", room_slug)
        ensure_dir(room_dir)
        for message in new_messages:
            write_jsonl(room_dir, message)

        max_message_id = last_message_id
        for message in messages:
            max_message_id = max(max_message_id, int(message.get("message_id") or 0))

        room_state[room_key] = {
            "name": room_name,
            "last_message_id": max_message_id,
        }
        print(f"Chatwork: {room_name}: +{len(new_messages)}")

    save_state(state)
    print("Chatwork: Sync complete.")


if __name__ == "__main__":
    sync()
