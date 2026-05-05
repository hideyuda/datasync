import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional, List

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def load_state() -> Dict:
    path = os.path.join("data", "state.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def save_state(state: Dict) -> None:
    ensure_dir("data")
    with open(os.path.join("data", "state.json"), "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def iter_channels(client: WebClient) -> List[Dict]:
    channels: List[Dict] = []
    cursor = None
    while True:
        try:
            resp = client.conversations_list(
                limit=1000,
                cursor=cursor,
                types="public_channel,private_channel",
            )
        except SlackApiError as e:
            print(f"Error listing channels: {e}")
            break
        channels.extend(resp.get("channels", []))
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return channels


def write_jsonl(channel_name: str, ts: float, message: Dict) -> None:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    ensure_dir(os.path.join("data", "slack", channel_name))
    path = os.path.join("data", "slack", channel_name, dt.strftime("%Y-%m-%d") + ".jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


def sync() -> None:
    token = env("SLACK_BOT_TOKEN")
    if not token:
        print("Slack: missing token, skipping.")
        return
    client = WebClient(token=token)
    state = load_state()
    ch_state = state.setdefault("channels", {})

    channels = iter_channels(client)
    print(f"Found {len(channels)} channels")

    for ch in channels:
        cid = ch["id"]
        name = ch.get("name") or cid
        last_ts = ch_state.get(cid, {}).get("last_ts")
        cursor = None
        fetched = 0
        while True:
            try:
                resp = client.conversations_history(
                    channel=cid, limit=1000, cursor=cursor, oldest=last_ts or "0"
                )
            except SlackApiError as e:
                print(f"History error {name}: {e}")
                break
            messages = resp.get("messages", [])
            for m in messages:
                try:
                    ts = float(m["ts"])
                except Exception:
                    continue
                write_jsonl(name, ts, m)
                fetched += 1
                if not last_ts or ts > float(last_ts):
                    last_ts = str(ts)
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        ch_state[cid] = {"name": name, "last_ts": last_ts}
        print(f"{name}: +{fetched}")
    save_state(state)
    print("Slack sync done.")


if __name__ == "__main__":
    sync()


