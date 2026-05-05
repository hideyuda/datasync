import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Set
from urllib.parse import quote

import requests


GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


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
        print(f"Teams: invalid integer for {name}={raw!r}, using {default}.")
        return default


def parse_csv(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_filter_set(raw: Optional[str]) -> Set[str]:
    return set(parse_csv(raw))


def safe_filename(value: str, fallback: str = "untitled", max_length: int = 120) -> str:
    value = re.sub(r"[^\w .-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip(" ._-")
    if not value:
        value = fallback
    return value[:max_length].strip(" ._-") or fallback


def parse_graph_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def message_day(message: Dict[str, Any]) -> str:
    created = parse_graph_datetime(message.get("createdDateTime"))
    if created:
        return created.date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()


def write_json(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_jsonl(path: str, item: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


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


@dataclass(frozen=True)
class TeamsConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    team_ids: List[str]
    channel_filters: Set[str]
    from_days: int
    include_replies: bool

    @classmethod
    def from_env(cls) -> Optional["TeamsConfig"]:
        tenant_id = env("TEAMS_TENANT_ID")
        client_id = env("TEAMS_CLIENT_ID")
        client_secret = env("TEAMS_CLIENT_SECRET")
        if not (tenant_id and client_id and client_secret):
            print("Teams: missing TEAMS_TENANT_ID, TEAMS_CLIENT_ID, or TEAMS_CLIENT_SECRET, skipping.")
            return None

        return cls(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            team_ids=parse_csv(env("TEAMS_TEAM_IDS")),
            channel_filters=parse_filter_set(env("TEAMS_CHANNEL_IDS")),
            from_days=max(1, env_int("TEAMS_FROM_DAYS", 30)),
            include_replies=env_bool("TEAMS_INCLUDE_REPLIES", False),
        )


class GraphClient:
    def __init__(self, config: TeamsConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self._access_token: Optional[str] = None

    def get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        token_url = (
            f"https://login.microsoftonline.com/{quote(self.config.tenant_id, safe='')}"
            "/oauth2/v2.0/token"
        )
        resp = requests.post(
            token_url,
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "grant_type": "client_credentials",
                "scope": GRAPH_SCOPE,
            },
            timeout=30,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("Teams: token response did not include access_token.")
        self._access_token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return token

    def get(self, path_or_url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self.get_access_token()
        url = path_or_url if path_or_url.startswith("https://") else f"{GRAPH_BASE}{path_or_url}"
        resp = self.session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            print(f"Teams: rate limited, sleeping {retry_after}s...")
            time.sleep(retry_after)
            resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def paged_get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        next_url: Optional[str] = None
        page_count = 0
        while True:
            if next_url:
                resp = self.get(next_url)
            else:
                resp = self.get(path, params)
            page_count += 1
            for item in resp.get("value", []):
                yield item

            next_url = resp.get("@odata.nextLink")
            if not next_url or (max_pages is not None and page_count >= max_pages):
                break

    def list_teams(self) -> List[Dict[str, Any]]:
        return list(
            self.paged_get(
                "/groups",
                params={
                    "$filter": "resourceProvisioningOptions/Any(x:x eq 'Team')",
                    "$select": "id,displayName,description,webUrl",
                    "$top": 999,
                },
            )
        )

    def get_team(self, team_id: str) -> Dict[str, Any]:
        return self.get(
            f"/teams/{quote(team_id, safe='')}",
            params={"$select": "id,displayName,description,webUrl"},
        )

    def list_channels(self, team_id: str) -> List[Dict[str, Any]]:
        return list(
            self.paged_get(
                f"/teams/{quote(team_id, safe='')}/channels",
                params={"$select": "id,displayName,description,email,webUrl,membershipType", "$top": 200},
            )
        )

    def list_channel_messages(self, team_id: str, channel_id: str) -> Iterable[Dict[str, Any]]:
        return self.paged_get(
            f"/teams/{quote(team_id, safe='')}/channels/{quote(channel_id, safe='')}/messages",
            params={"$top": 50},
        )

    def list_message_replies(self, team_id: str, channel_id: str, message_id: str) -> List[Dict[str, Any]]:
        return list(
            self.paged_get(
                (
                    f"/teams/{quote(team_id, safe='')}/channels/{quote(channel_id, safe='')}"
                    f"/messages/{quote(message_id, safe='')}/replies"
                ),
                params={"$top": 50},
            )
        )


def team_slug(team: Dict[str, Any]) -> str:
    team_id = str(team.get("id") or "unknown")
    name = safe_filename(str(team.get("displayName") or ""), "team")
    return f"{name}_{team_id}"


def channel_slug(channel: Dict[str, Any]) -> str:
    channel_id = str(channel.get("id") or "unknown")
    name = safe_filename(str(channel.get("displayName") or ""), "channel")
    return f"{name}_{channel_id}"


def channel_allowed(team_id: str, channel_id: str, filters: Set[str]) -> bool:
    if not filters:
        return True
    return channel_id in filters or f"{team_id}/{channel_id}" in filters


def message_created_after(message: Dict[str, Any], threshold: datetime) -> bool:
    created = parse_graph_datetime(message.get("createdDateTime"))
    return created is not None and created > threshold


def state_key(team_id: str, channel_id: str) -> str:
    return f"{team_id}/{channel_id}"


def message_output_path(team: Dict[str, Any], channel: Dict[str, Any], message: Dict[str, Any]) -> str:
    return os.path.join(
        "data",
        "messages",
        team_slug(team),
        channel_slug(channel),
        message_day(message) + ".jsonl",
    )


def normalize_message(message: Dict[str, Any], replies: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    normalized = dict(message)
    if replies is not None:
        normalized["replies"] = replies
    return normalized


def write_message(team: Dict[str, Any], channel: Dict[str, Any], message: Dict[str, Any]) -> None:
    append_jsonl(message_output_path(team, channel, message), message)


def save_team_metadata(team: Dict[str, Any]) -> None:
    write_json(os.path.join("data", "teams", team_slug(team) + ".json"), team)


def save_channel_metadata(team: Dict[str, Any], channel: Dict[str, Any]) -> None:
    write_json(os.path.join("data", "channels", team_slug(team), channel_slug(channel) + ".json"), channel)


def resolve_teams(client: GraphClient, configured_team_ids: List[str]) -> List[Dict[str, Any]]:
    if configured_team_ids:
        teams: List[Dict[str, Any]] = []
        for team_id in configured_team_ids:
            try:
                teams.append(client.get_team(team_id))
            except requests.HTTPError as e:
                print(f"Teams: failed to fetch team {team_id}: {e}")
        return teams

    print("Teams: TEAMS_TEAM_IDS not set, listing Teams-backed groups...")
    try:
        return client.list_teams()
    except requests.HTTPError as e:
        print(f"Teams: failed to list teams. Set TEAMS_TEAM_IDS or add team read scopes. {e}")
        return []


def sync_channel_messages(
    client: GraphClient,
    team: Dict[str, Any],
    channel: Dict[str, Any],
    state: Dict[str, Any],
    cutoff: datetime,
    include_replies: bool,
) -> int:
    team_id = str(team["id"])
    channel_id = str(channel["id"])
    channel_state = state.setdefault("channels", {}).setdefault(state_key(team_id, channel_id), {})
    last_created = parse_graph_datetime(channel_state.get("last_created_datetime"))
    threshold = max([dt for dt in [cutoff, last_created] if dt is not None])

    seen_ids = set(channel_state.get("seen_message_ids") or [])
    new_messages: List[Dict[str, Any]] = []
    fetched_any_older = False

    for message in client.list_channel_messages(team_id, channel_id):
        message_id = str(message.get("id") or "")
        created = parse_graph_datetime(message.get("createdDateTime"))
        if created is not None and created <= threshold:
            fetched_any_older = True
            break
        if not message_id or message_id in seen_ids:
            continue

        replies = None
        if include_replies:
            try:
                replies = client.list_message_replies(team_id, channel_id, message_id)
            except requests.HTTPError as e:
                print(f"Teams: failed to fetch replies for message {message_id}: {e}")
        new_messages.append(normalize_message(message, replies))

    new_messages.sort(key=lambda item: item.get("createdDateTime") or "")
    for message in new_messages:
        write_message(team, channel, message)

    for message in new_messages:
        message_id = str(message.get("id") or "")
        if message_id:
            seen_ids.add(message_id)

    max_created = last_created
    for message in new_messages:
        created = parse_graph_datetime(message.get("createdDateTime"))
        if created and (max_created is None or created > max_created):
            max_created = created

    channel_state.update(
        {
            "team_name": team.get("displayName"),
            "channel_name": channel.get("displayName"),
            "last_message_id": new_messages[-1].get("id") if new_messages else channel_state.get("last_message_id"),
            "last_created_datetime": max_created.isoformat() if max_created else channel_state.get("last_created_datetime"),
            "seen_message_ids": sorted(seen_ids)[-500:],
            "stopped_at_existing_cursor": fetched_any_older,
        }
    )
    return len(new_messages)


def sync() -> None:
    config = TeamsConfig.from_env()
    if config is None:
        return

    client = GraphClient(config)
    state = load_state()
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.from_days)
    teams = resolve_teams(client, config.team_ids)
    if not teams:
        print("Teams: no teams to sync.")
        save_state(state)
        return

    total_channels = 0
    total_messages = 0
    for team in teams:
        team_id = str(team.get("id") or "")
        if not team_id:
            continue
        save_team_metadata(team)
        try:
            channels = client.list_channels(team_id)
        except requests.HTTPError as e:
            print(f"Teams: failed to list channels for {team.get('displayName') or team_id}: {e}")
            continue

        for channel in channels:
            channel_id = str(channel.get("id") or "")
            if not channel_id or not channel_allowed(team_id, channel_id, config.channel_filters):
                continue
            total_channels += 1
            save_channel_metadata(team, channel)
            try:
                count = sync_channel_messages(
                    client,
                    team,
                    channel,
                    state,
                    cutoff,
                    config.include_replies,
                )
            except requests.HTTPError as e:
                print(f"Teams: failed to sync channel {channel.get('displayName') or channel_id}: {e}")
                continue
            total_messages += count
            print(f"Teams: {team.get('displayName')} / {channel.get('displayName')}: +{count}")

    state["summary"] = {
        "teams": len(teams),
        "channels": total_channels,
        "messages": total_messages,
    }
    save_state(state)
    print(f"Teams: Sync complete. {total_channels} channel(s), {total_messages} message(s).")


if __name__ == "__main__":
    sync()
