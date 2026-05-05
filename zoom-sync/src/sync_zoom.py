import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import requests


API_BASE = "https://api.zoom.us/v2"
TOKEN_URL = "https://zoom.us/oauth/token"
MAX_RECORDING_RANGE_DAYS = 30


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def env_bool(name: str, default: bool = False) -> bool:
    raw = env(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    raw = env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"Zoom: invalid integer for {name}={raw!r}, using {default}.")
        return default


def load_state() -> Dict[str, Any]:
    path = os.path.join("data", "state.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: Dict[str, Any]) -> None:
    ensure_dir("data")
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(os.path.join("data", "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def save_json(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_text(path: str, content: str) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def safe_filename(value: str, fallback: str = "untitled", max_length: int = 120) -> str:
    value = re.sub(r"[^\w .-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip(" ._-")
    if not value:
        value = fallback
    return value[:max_length].strip(" ._-") or fallback


def parse_csv(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_zoom_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def date_windows(from_day: date, to_day: date) -> Iterable[Tuple[date, date]]:
    current = from_day
    while current <= to_day:
        window_end = min(current + timedelta(days=MAX_RECORDING_RANGE_DAYS - 1), to_day)
        yield current, window_end
        current = window_end + timedelta(days=1)


@dataclass(frozen=True)
class ZoomConfig:
    account_id: str
    client_id: str
    client_secret: str
    user_ids: List[str]
    from_days: int
    download_recordings: bool

    @classmethod
    def from_env(cls) -> Optional["ZoomConfig"]:
        account_id = env("ZOOM_ACCOUNT_ID")
        client_id = env("ZOOM_CLIENT_ID")
        client_secret = env("ZOOM_CLIENT_SECRET")
        if not (account_id and client_id and client_secret):
            print("Zoom: missing ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, or ZOOM_CLIENT_SECRET, skipping.")
            return None

        return cls(
            account_id=account_id,
            client_id=client_id,
            client_secret=client_secret,
            user_ids=parse_csv(env("ZOOM_USER_IDS")),
            from_days=max(1, env_int("ZOOM_FROM_DAYS", 30)),
            download_recordings=env_bool("ZOOM_DOWNLOAD_RECORDINGS", False),
        )


class ZoomClient:
    def __init__(self, config: ZoomConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self._access_token: Optional[str] = None

    def get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        resp = requests.post(
            TOKEN_URL,
            params={
                "grant_type": "account_credentials",
                "account_id": self.config.account_id,
            },
            auth=(self.config.client_id, self.config.client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("Zoom: token response did not include access_token.")
        self._access_token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return token

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self.get_access_token()
        url = f"{API_BASE}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            print(f"Zoom: rate limited, sleeping {retry_after}s...")
            time.sleep(retry_after)
            resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def paged_get(
        self,
        path: str,
        collection_key: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        next_page_token: Optional[str] = None
        while True:
            page_params = dict(params or {})
            if next_page_token:
                page_params["next_page_token"] = next_page_token
            resp = self.get(path, page_params)
            items.extend(resp.get(collection_key, []))
            next_page_token = resp.get("next_page_token")
            if not next_page_token:
                break
        return items

    def list_users(self) -> List[Dict[str, Any]]:
        return self.paged_get(
            "/users",
            "users",
            params={"status": "active", "page_size": 300},
        )

    def list_recordings(self, user_id: str, from_day: date, to_day: date) -> List[Dict[str, Any]]:
        meetings: List[Dict[str, Any]] = []
        for start_day, end_day in date_windows(from_day, to_day):
            path = f"/users/{quote(user_id, safe='')}/recordings"
            meetings.extend(
                self.paged_get(
                    path,
                    "meetings",
                    params={
                        "from": start_day.isoformat(),
                        "to": end_day.isoformat(),
                        "page_size": 300,
                    },
                )
            )
        return meetings

    def download_file(self, download_url: str) -> bytes:
        self.get_access_token()
        resp = self.session.get(download_url, timeout=120)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            print(f"Zoom: download rate limited, sleeping {retry_after}s...")
            time.sleep(retry_after)
            resp = self.session.get(download_url, timeout=120)
        resp.raise_for_status()
        return resp.content


def meeting_day(meeting: Dict[str, Any]) -> str:
    started = parse_zoom_time(meeting.get("start_time"))
    if started:
        return started.date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()


def meeting_file_stem(meeting: Dict[str, Any]) -> str:
    topic = safe_filename(meeting.get("topic") or "", "meeting")
    uuid = safe_filename(meeting.get("uuid") or meeting.get("id") or "unknown", "unknown")
    return f"{topic}_{uuid}"


def write_meeting_files(meeting: Dict[str, Any]) -> None:
    day = meeting_day(meeting)
    stem = meeting_file_stem(meeting)
    base_path = os.path.join("data", "meetings", day, stem)
    save_json(f"{base_path}.json", meeting)
    save_text(f"{base_path}.md", render_meeting_markdown(meeting))


def render_meeting_markdown(meeting: Dict[str, Any]) -> str:
    files = meeting.get("recording_files") or []
    lines = [
        f"# {meeting.get('topic') or '(no title)'}",
        "",
        f"- UUID: `{meeting.get('uuid') or ''}`",
        f"- ID: `{meeting.get('id') or ''}`",
        f"- Host: {meeting.get('host_email') or meeting.get('host_id') or ''}",
        f"- Start: {meeting.get('start_time') or ''}",
        f"- Duration: {meeting.get('duration') or 0} minutes",
        f"- Share URL: {meeting.get('share_url') or ''}",
        "",
        "## Recording Files",
        "",
    ]
    if not files:
        lines.append("- No recording files found.")
    for item in files:
        lines.append(
            "- "
            + f"`{item.get('file_type') or ''}` "
            + f"{item.get('recording_type') or ''} "
            + f"({item.get('status') or 'unknown'}) "
            + f"id=`{item.get('id') or ''}`"
        )
    return "\n".join(lines) + "\n"


def recording_extension(recording_file: Dict[str, Any]) -> str:
    ext = recording_file.get("file_extension")
    if ext:
        return str(ext).lower()
    file_type = str(recording_file.get("file_type") or "").lower()
    return {
        "transcript": "vtt",
        "chat": "txt",
        "timeline": "json",
        "mp4": "mp4",
        "m4a": "m4a",
    }.get(file_type, "bin")


def should_download(recording_file: Dict[str, Any], download_recordings: bool) -> bool:
    file_type = str(recording_file.get("file_type") or "").upper()
    if file_type == "TRANSCRIPT":
        return True
    return download_recordings


def download_recording_file(
    client: ZoomClient,
    meeting: Dict[str, Any],
    recording_file: Dict[str, Any],
    state: Dict[str, Any],
    download_recordings: bool,
) -> bool:
    file_id = recording_file.get("id")
    download_url = recording_file.get("download_url")
    if not file_id or not download_url:
        return False
    if not should_download(recording_file, download_recordings):
        return False

    file_state = state.setdefault("recording_files", {})
    if file_id in file_state:
        return False

    file_type = str(recording_file.get("file_type") or "").upper()
    day = meeting_day(meeting)
    stem = meeting_file_stem(meeting)
    extension = recording_extension(recording_file)
    if file_type == "TRANSCRIPT":
        output_dir = os.path.join("data", "transcripts", day)
    else:
        output_dir = os.path.join("data", "recording_files", day)
    path = os.path.join(output_dir, f"{stem}_{safe_filename(file_id, 'file')}.{extension}")

    try:
        data = client.download_file(download_url)
    except requests.HTTPError as e:
        print(f"Zoom: failed to download recording file {file_id}: {e}")
        return False

    ensure_dir(output_dir)
    mode = "wb"
    with open(path, mode) as f:
        f.write(data)

    file_state[file_id] = {
        "meeting_uuid": meeting.get("uuid"),
        "file_type": recording_file.get("file_type"),
        "recording_type": recording_file.get("recording_type"),
        "path": path,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    return True


def resolve_user_ids(client: ZoomClient, configured_user_ids: List[str]) -> List[str]:
    if configured_user_ids:
        return configured_user_ids

    print("Zoom: ZOOM_USER_IDS not set, listing active account users...")
    try:
        users = client.list_users()
    except requests.HTTPError as e:
        print(f"Zoom: failed to list users. Set ZOOM_USER_IDS or add user read scopes. {e}")
        return []

    user_ids = [user.get("id") or user.get("email") for user in users]
    return [str(user_id) for user_id in user_ids if user_id]


def sync() -> None:
    config = ZoomConfig.from_env()
    if config is None:
        return

    client = ZoomClient(config)
    state = load_state()
    users_state = state.setdefault("users", {})
    today = datetime.now(timezone.utc).date()
    from_day = today - timedelta(days=config.from_days)
    user_ids = resolve_user_ids(client, config.user_ids)

    if not user_ids:
        print("Zoom: no users to sync.")
        save_state(state)
        return

    total_meetings = 0
    total_downloads = 0
    for user_id in user_ids:
        print(f"Zoom: fetching recordings for {user_id} from {from_day} to {today}...")
        try:
            meetings = client.list_recordings(user_id, from_day, today)
        except requests.HTTPError as e:
            print(f"Zoom: error fetching recordings for {user_id}: {e}")
            continue

        total_meetings += len(meetings)
        for meeting in meetings:
            write_meeting_files(meeting)
            for recording_file in meeting.get("recording_files") or []:
                if download_recording_file(
                    client,
                    meeting,
                    recording_file,
                    state,
                    config.download_recordings,
                ):
                    total_downloads += 1

        users_state[user_id] = {
            "last_synced_from": from_day.isoformat(),
            "last_synced_to": today.isoformat(),
            "meetings": len(meetings),
        }
        print(f"Zoom: {user_id}: {len(meetings)} meeting(s).")

    state["summary"] = {
        "meetings": total_meetings,
        "downloads": total_downloads,
    }
    save_state(state)
    print(f"Zoom: Sync complete. {total_meetings} meeting(s), {total_downloads} file(s) downloaded.")


if __name__ == "__main__":
    sync()
