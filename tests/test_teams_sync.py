import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_teams_module():
    module_path = Path(__file__).resolve().parents[1] / "teams" / "src" / "sync_teams.py"
    spec = importlib.util.spec_from_file_location("sync_teams", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


teams = load_teams_module()


def test_safe_filename_replaces_unsafe_characters_and_trims():
    assert teams.safe_filename("  Sales / Weekly: Sync?  ") == "Sales _ Weekly_ Sync"


def test_safe_filename_uses_fallback_for_empty_values():
    assert teams.safe_filename("///", fallback="channel") == "channel"


def test_parse_csv_ignores_empty_items_and_whitespace():
    assert teams.parse_csv("team-1, team-2, , team-3 ") == ["team-1", "team-2", "team-3"]


def test_parse_graph_datetime_returns_utc_datetime():
    parsed = teams.parse_graph_datetime("2026-05-05T08:00:00Z")

    assert parsed == datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc)


def test_channel_allowed_accepts_channel_or_scoped_filter():
    filters = {"channel-1", "team-2/channel-2"}

    assert teams.channel_allowed("team-1", "channel-1", filters) is True
    assert teams.channel_allowed("team-2", "channel-2", filters) is True
    assert teams.channel_allowed("team-1", "channel-2", filters) is False


def test_message_output_path_buckets_by_created_date():
    team = {"id": "team-1", "displayName": "Core Team"}
    channel = {"id": "channel-1", "displayName": "General"}
    message = {"createdDateTime": "2026-05-05T08:30:00Z"}

    assert (
        teams.message_output_path(team, channel, message)
        == "data/messages/Core Team_team-1/General_channel-1/2026-05-05.jsonl"
    )


def test_normalize_message_includes_replies_when_provided():
    normalized = teams.normalize_message({"id": "message-1"}, replies=[{"id": "reply-1"}])

    assert normalized["id"] == "message-1"
    assert normalized["replies"] == [{"id": "reply-1"}]


def test_graph_client_paged_get_follows_odata_next_link():
    config = teams.TeamsConfig(
        tenant_id="tenant",
        client_id="client",
        client_secret="secret",
        team_ids=[],
        channel_filters=set(),
        from_days=30,
        include_replies=False,
    )
    client = teams.GraphClient(config)
    calls = []

    def fake_get(path_or_url, params=None):
        calls.append((path_or_url, params))
        if len(calls) == 1:
            return {
                "value": [{"id": "first"}],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/next",
            }
        return {"value": [{"id": "second"}]}

    client.get = fake_get

    assert list(client.paged_get("/items", params={"$top": 1})) == [
        {"id": "first"},
        {"id": "second"},
    ]
    assert calls == [
        ("/items", {"$top": 1}),
        ("https://graph.microsoft.com/v1.0/next", None),
    ]


def test_sync_channel_messages_writes_new_messages_and_updates_state(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    team = {"id": "team-1", "displayName": "Core Team"}
    channel = {"id": "channel-1", "displayName": "General"}
    messages = [
        {"id": "newer", "createdDateTime": "2026-05-05T09:00:00Z", "body": {"content": "newer"}},
        {"id": "older", "createdDateTime": "2026-05-05T08:00:00Z", "body": {"content": "older"}},
    ]

    class FakeClient:
        def list_channel_messages(self, team_id, channel_id):
            assert team_id == "team-1"
            assert channel_id == "channel-1"
            return iter(messages)

    state = {}
    count = teams.sync_channel_messages(
        FakeClient(),
        team,
        channel,
        state,
        datetime(2026, 5, 5, 7, 0, tzinfo=timezone.utc),
        include_replies=False,
    )

    output = tmp_path / "data/messages/Core Team_team-1/General_channel-1/2026-05-05.jsonl"
    assert count == 2
    assert output.exists()
    assert state["channels"]["team-1/channel-1"]["last_message_id"] == "newer"
    assert state["channels"]["team-1/channel-1"]["last_created_datetime"] == "2026-05-05T09:00:00+00:00"


def test_sync_channel_messages_stops_at_existing_cursor(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    team = {"id": "team-1", "displayName": "Core Team"}
    channel = {"id": "channel-1", "displayName": "General"}
    messages = [
        {"id": "newer", "createdDateTime": "2026-05-05T09:00:00Z"},
        {"id": "old-cursor", "createdDateTime": "2026-05-05T08:00:00Z"},
    ]

    class FakeClient:
        def list_channel_messages(self, team_id, channel_id):
            return iter(messages)

    state = {
        "channels": {
            "team-1/channel-1": {
                "last_created_datetime": "2026-05-05T08:00:00+00:00",
                "seen_message_ids": ["old-cursor"],
            }
        }
    }

    count = teams.sync_channel_messages(
        FakeClient(),
        team,
        channel,
        state,
        datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
        include_replies=False,
    )

    assert count == 1
    assert state["channels"]["team-1/channel-1"]["last_message_id"] == "newer"
    assert state["channels"]["team-1/channel-1"]["stopped_at_existing_cursor"] is True
