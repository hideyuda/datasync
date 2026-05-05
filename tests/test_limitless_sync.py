import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_limitless_module():
    module_path = Path(__file__).resolve().parents[1] / "limitless" / "src" / "sync_limitless.py"
    spec = importlib.util.spec_from_file_location("sync_limitless", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


limitless = load_limitless_module()


def test_safe_filename_replaces_unsafe_characters_and_trims():
    assert limitless.safe_filename("  Pendant / Morning: Walk?  ") == "Pendant _ Morning_ Walk"


def test_safe_filename_uses_fallback_for_empty_values():
    assert limitless.safe_filename("///", fallback="lifelog") == "lifelog"


def test_parse_csv_ignores_empty_items_and_whitespace():
    assert limitless.parse_csv("a, b, , c ") == ["a", "b", "c"]


def test_parse_limitless_time_returns_utc_datetime():
    parsed = limitless.parse_limitless_time("2026-05-05T08:00:00Z")

    assert parsed == datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc)


def test_lifelog_paths_bucket_by_start_date():
    lifelog = {
        "id": "life-1",
        "title": "Morning Walk",
        "startTime": "2026-05-05T08:00:00Z",
    }

    assert limitless.lifelog_base_path(lifelog) == "data/lifelogs/2026-05-05/Morning Walk_life-1"
    assert limitless.contents_path(lifelog) == "data/contents/2026-05-05/Morning Walk_life-1.jsonl"
    assert limitless.audio_path(lifelog) == "data/audio/2026-05-05/Morning Walk_life-1.ogg"


def test_extract_lifelogs_supports_common_response_shapes():
    assert limitless.extract_lifelogs({"data": [{"id": "a"}]}) == [{"id": "a"}]
    assert limitless.extract_lifelogs({"lifelogs": [{"id": "b"}]}) == [{"id": "b"}]
    assert limitless.extract_lifelogs({"data": {"lifelogs": [{"id": "c"}]}}) == [{"id": "c"}]


def test_extract_next_cursor_supports_meta_shapes():
    assert limitless.extract_next_cursor({"meta": {"lifelogs": {"nextCursor": "cursor-1"}}}) == "cursor-1"
    assert limitless.extract_next_cursor({"meta": {"nextCursor": "cursor-2"}}) == "cursor-2"
    assert limitless.extract_next_cursor({"nextCursor": "cursor-3"}) == "cursor-3"


def test_render_lifelog_markdown_prefers_api_markdown():
    assert limitless.render_lifelog_markdown({"markdown": "# Existing\n"}) == "# Existing\n"


def test_render_lifelog_markdown_falls_back_to_contents():
    markdown = limitless.render_lifelog_markdown(
        {
            "id": "life-1",
            "title": "Morning Walk",
            "startTime": "2026-05-05T08:00:00Z",
            "endTime": "2026-05-05T08:30:00Z",
            "updatedAt": "2026-05-05T09:00:00Z",
            "isStarred": True,
            "contents": [
                {
                    "speakerName": "Alice",
                    "startTime": "2026-05-05T08:01:00Z",
                    "content": "Hello",
                }
            ],
        }
    )

    assert "# Morning Walk" in markdown
    assert "- ID: `life-1`" in markdown
    assert "- **Alice** (2026-05-05T08:01:00Z): Hello" in markdown


def test_paged_lifelogs_follows_cursor():
    config = limitless.LimitlessConfig(
        api_key="key",
        from_days=30,
        timezone="UTC",
        include_contents=True,
        include_audio=False,
    )
    client = limitless.LimitlessClient(config)
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        if len(calls) == 1:
            return {
                "data": [{"id": "first"}],
                "meta": {"lifelogs": {"nextCursor": "next"}},
            }
        return {"data": [{"id": "second"}]}

    client.get = fake_get
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end = datetime(2026, 5, 5, tzinfo=timezone.utc)

    assert list(client.paged_lifelogs(start, end, include_markdown=True, include_contents=True)) == [
        {"id": "first"},
        {"id": "second"},
    ]
    assert calls[0][1]["limit"] == 10
    assert calls[0][1]["includeMarkdown"] == "true"
    assert calls[1][1]["cursor"] == "next"


def test_write_lifelog_writes_json_markdown_and_contents(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    lifelog = {
        "id": "life-1",
        "title": "Morning Walk",
        "startTime": "2026-05-05T08:00:00Z",
        "markdown": "# Morning Walk",
        "contents": [{"content": "Hello"}],
    }

    result = limitless.write_lifelog(lifelog, include_contents=True)

    assert result == {"json": True, "markdown": True, "contents": True}
    assert (tmp_path / "data/lifelogs/2026-05-05/Morning Walk_life-1.json").exists()
    assert (tmp_path / "data/lifelogs/2026-05-05/Morning Walk_life-1.md").exists()
    assert (tmp_path / "data/contents/2026-05-05/Morning Walk_life-1.jsonl").exists()


def test_sync_lifelogs_updates_state_and_counts_new_items(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = limitless.LimitlessConfig(
        api_key="key",
        from_days=30,
        timezone="UTC",
        include_contents=True,
        include_audio=False,
    )
    lifelogs = [
        {
            "id": "known",
            "title": "Known",
            "startTime": "2026-05-05T08:00:00Z",
            "contents": [{"content": "updated"}],
        },
        {
            "id": "new",
            "title": "New",
            "startTime": "2026-05-05T09:00:00Z",
            "contents": [{"content": "fresh"}],
        },
    ]

    class FakeClient:
        def paged_lifelogs(self, start, end, include_markdown, include_contents):
            assert include_markdown is True
            assert include_contents is True
            return iter(lifelogs)

    state = {"seen_lifelog_ids": ["known"]}
    summary = limitless.sync_lifelogs(
        FakeClient(),
        config,
        state,
        datetime(2026, 5, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 5, tzinfo=timezone.utc),
    )

    assert summary == {"lifelogs": 2, "new_lifelogs": 1, "contents": 2, "audio": 0}
    assert state["seen_lifelog_ids"] == ["known", "new"]
    assert state["last_synced_start"] == "2026-05-01T00:00:00Z"
    assert (tmp_path / "data/lifelogs/2026-05-05/New_new.md").exists()
