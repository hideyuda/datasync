import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests


API_BASE = "https://api.limitless.ai"


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
        print(f"Limitless: invalid integer for {name}={raw!r}, using {default}.")
        return default


def parse_csv(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def safe_filename(value: str, fallback: str = "untitled", max_length: int = 120) -> str:
    value = re.sub(r"[^\w .-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip(" ._-")
    if not value:
        value = fallback
    return value[:max_length].strip(" ._-") or fallback


def parse_limitless_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def save_bytes(path: str, content: bytes) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "wb") as f:
        f.write(content)


@dataclass(frozen=True)
class LimitlessConfig:
    api_key: str
    from_days: int
    timezone: str
    include_contents: bool
    include_audio: bool

    @classmethod
    def from_env(cls) -> Optional["LimitlessConfig"]:
        api_key = env("LIMITLESS_API_KEY")
        if not api_key:
            print("Limitless: missing LIMITLESS_API_KEY, skipping.")
            return None

        return cls(
            api_key=api_key,
            from_days=max(1, env_int("LIMITLESS_FROM_DAYS", 30)),
            timezone=env("LIMITLESS_TIMEZONE", "UTC") or "UTC",
            include_contents=env_bool("LIMITLESS_INCLUDE_CONTENTS", True),
            include_audio=env_bool("LIMITLESS_INCLUDE_AUDIO", False),
        )


class LimitlessClient:
    def __init__(self, config: LimitlessConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": config.api_key})

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = path if path.startswith("https://") else f"{API_BASE}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            retry_after = parse_retry_after(resp)
            print(f"Limitless: rate limited, sleeping {retry_after}s...")
            time.sleep(retry_after)
            resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        if resp.content:
            content_type = resp.headers.get("Content-Type", "")
            if content_type.startswith("application/json"):
                return resp.json()
        return resp

    def paged_lifelogs(
        self,
        start: datetime,
        end: datetime,
        include_markdown: bool,
        include_contents: bool,
    ) -> Iterable[Dict[str, Any]]:
        cursor: Optional[str] = None
        while True:
            params: Dict[str, Any] = {
                "start": isoformat_utc(start),
                "end": isoformat_utc(end),
                "timezone": self.config.timezone,
                "direction": "asc",
                "limit": 10,
                "includeMarkdown": str(include_markdown).lower(),
                "includeContents": str(include_contents).lower(),
            }
            if cursor:
                params["cursor"] = cursor

            resp = self.get("/v1/lifelogs", params=params)
            lifelogs = extract_lifelogs(resp)
            for lifelog in lifelogs:
                yield lifelog

            cursor = extract_next_cursor(resp)
            if not cursor:
                break

    def download_audio(self, start: datetime, end: datetime) -> bytes:
        resp = self.session.get(
            f"{API_BASE}/v1/download-audio",
            params={
                "start": isoformat_utc(start),
                "end": isoformat_utc(end),
                "timezone": self.config.timezone,
            },
            timeout=120,
        )
        if resp.status_code == 429:
            retry_after = parse_retry_after(resp)
            print(f"Limitless: audio download rate limited, sleeping {retry_after}s...")
            time.sleep(retry_after)
            resp = self.session.get(resp.url, timeout=120)
        resp.raise_for_status()
        return resp.content


def parse_retry_after(resp: requests.Response) -> int:
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return int(header)
        except ValueError:
            pass
    try:
        body = resp.json()
    except ValueError:
        return 60
    for key in ("retryAfter", "retry_after"):
        if key in body:
            try:
                return int(body[key])
            except (TypeError, ValueError):
                return 60
    return 60


def extract_lifelogs(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(response.get("data"), list):
        return response.get("data", [])
    if isinstance(response.get("lifelogs"), list):
        return response.get("lifelogs", [])
    data = response.get("data") or {}
    if isinstance(data, dict) and isinstance(data.get("lifelogs"), list):
        return data.get("lifelogs", [])
    return []


def extract_next_cursor(response: Dict[str, Any]) -> Optional[str]:
    meta = response.get("meta") or {}
    lifelogs_meta = meta.get("lifelogs") if isinstance(meta, dict) else None
    if isinstance(lifelogs_meta, dict) and lifelogs_meta.get("nextCursor"):
        return str(lifelogs_meta["nextCursor"])
    if isinstance(meta, dict) and meta.get("nextCursor"):
        return str(meta["nextCursor"])
    if response.get("nextCursor"):
        return str(response["nextCursor"])
    return None


def lifelog_id(lifelog: Dict[str, Any]) -> str:
    return str(lifelog.get("id") or lifelog.get("lifelogId") or "")


def lifelog_title(lifelog: Dict[str, Any]) -> str:
    return str(lifelog.get("title") or lifelog.get("name") or "lifelog")


def lifelog_day(lifelog: Dict[str, Any]) -> str:
    started = parse_limitless_time(lifelog.get("startTime") or lifelog.get("start"))
    if started:
        return started.date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()


def lifelog_file_stem(lifelog: Dict[str, Any]) -> str:
    fallback_id = lifelog_id(lifelog) or "unknown"
    title = safe_filename(lifelog_title(lifelog), "lifelog")
    safe_id = safe_filename(fallback_id, "unknown")
    return f"{title}_{safe_id}"


def lifelog_base_path(lifelog: Dict[str, Any]) -> str:
    return os.path.join("data", "lifelogs", lifelog_day(lifelog), lifelog_file_stem(lifelog))


def contents_path(lifelog: Dict[str, Any]) -> str:
    return os.path.join("data", "contents", lifelog_day(lifelog), lifelog_file_stem(lifelog) + ".jsonl")


def audio_path(lifelog: Dict[str, Any]) -> str:
    return os.path.join("data", "audio", lifelog_day(lifelog), lifelog_file_stem(lifelog) + ".ogg")


def render_lifelog_markdown(lifelog: Dict[str, Any]) -> str:
    markdown = lifelog.get("markdown")
    if markdown:
        return str(markdown).rstrip() + "\n"

    lines = [
        f"# {lifelog_title(lifelog)}",
        "",
        f"- ID: `{lifelog_id(lifelog)}`",
        f"- Start: {lifelog.get('startTime') or ''}",
        f"- End: {lifelog.get('endTime') or ''}",
        f"- Updated: {lifelog.get('updatedAt') or ''}",
        f"- Starred: {lifelog.get('isStarred')}",
        "",
    ]
    contents = lifelog.get("contents") or []
    if contents:
        lines.append("## Contents")
        lines.append("")
        for item in contents:
            speaker = item.get("speakerName") or item.get("speakerIdentifier") or "Unknown"
            content = item.get("content") or ""
            start = item.get("startTime") or item.get("startOffsetMs") or ""
            lines.append(f"- **{speaker}** ({start}): {content}")
    return "\n".join(lines).rstrip() + "\n"


def write_contents(lifelog: Dict[str, Any]) -> bool:
    contents = lifelog.get("contents") or []
    if not contents:
        return False

    path = contents_path(lifelog)
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        for item in contents:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return True


def write_lifelog(lifelog: Dict[str, Any], include_contents: bool) -> Dict[str, bool]:
    base_path = lifelog_base_path(lifelog)
    save_json(base_path + ".json", lifelog)
    save_text(base_path + ".md", render_lifelog_markdown(lifelog))
    wrote_contents = write_contents(lifelog) if include_contents else False
    return {"json": True, "markdown": True, "contents": wrote_contents}


def download_audio_for_lifelog(client: LimitlessClient, lifelog: Dict[str, Any]) -> bool:
    start = parse_limitless_time(lifelog.get("startTime") or lifelog.get("start"))
    end = parse_limitless_time(lifelog.get("endTime") or lifelog.get("end"))
    if not (start and end):
        return False

    try:
        audio = client.download_audio(start, end)
    except requests.HTTPError as e:
        print(f"Limitless: failed to download audio for {lifelog_id(lifelog)}: {e}")
        return False

    save_bytes(audio_path(lifelog), audio)
    return True


def sync_lifelogs(
    client: LimitlessClient,
    config: LimitlessConfig,
    state: Dict[str, Any],
    start: datetime,
    end: datetime,
) -> Dict[str, int]:
    seen_ids = set(state.get("seen_lifelog_ids") or [])
    processed_ids = set(seen_ids)
    total = 0
    new_count = 0
    contents_count = 0
    audio_count = 0

    for lifelog in client.paged_lifelogs(
        start=start,
        end=end,
        include_markdown=True,
        include_contents=config.include_contents,
    ):
        current_id = lifelog_id(lifelog)
        if not current_id:
            continue

        total += 1
        is_new = current_id not in seen_ids
        results = write_lifelog(lifelog, config.include_contents)
        if is_new:
            new_count += 1
        if results["contents"]:
            contents_count += 1
        if config.include_audio and download_audio_for_lifelog(client, lifelog):
            audio_count += 1
        processed_ids.add(current_id)

    state["seen_lifelog_ids"] = sorted(processed_ids)[-5000:]
    state["last_synced_start"] = isoformat_utc(start)
    state["last_synced_end"] = isoformat_utc(end)
    return {
        "lifelogs": total,
        "new_lifelogs": new_count,
        "contents": contents_count,
        "audio": audio_count,
    }


def sync() -> None:
    config = LimitlessConfig.from_env()
    if config is None:
        return

    client = LimitlessClient(config)
    state = load_state()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=config.from_days)

    summary = sync_lifelogs(client, config, state, start, end)
    state["summary"] = summary
    save_state(state)
    print(
        "Limitless: Sync complete. "
        f"{summary['lifelogs']} lifelog(s), {summary['new_lifelogs']} new, "
        f"{summary['contents']} contents file(s), {summary['audio']} audio file(s)."
    )


if __name__ == "__main__":
    sync()
