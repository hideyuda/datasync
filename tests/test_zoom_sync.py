import importlib.util
import sys
from datetime import date
from pathlib import Path


def load_zoom_module():
    module_path = Path(__file__).resolve().parents[1] / "zoom" / "src" / "sync_zoom.py"
    spec = importlib.util.spec_from_file_location("sync_zoom", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


zoom = load_zoom_module()


def test_safe_filename_replaces_unsafe_characters_and_trims():
    assert zoom.safe_filename("  Team / Weekly: Sync?  ") == "Team _ Weekly_ Sync"


def test_safe_filename_uses_fallback_for_empty_values():
    assert zoom.safe_filename("///", fallback="meeting") == "meeting"


def test_parse_csv_ignores_empty_items_and_whitespace():
    assert zoom.parse_csv("alice@example.com, bob@example.com, , carol@example.com ") == [
        "alice@example.com",
        "bob@example.com",
        "carol@example.com",
    ]


def test_date_windows_split_zoom_recording_range_limit():
    windows = list(zoom.date_windows(date(2026, 1, 1), date(2026, 2, 15)))

    assert windows == [
        (date(2026, 1, 1), date(2026, 1, 30)),
        (date(2026, 1, 31), date(2026, 2, 15)),
    ]


def test_recording_extension_prefers_explicit_extension():
    assert zoom.recording_extension({"file_type": "TRANSCRIPT", "file_extension": "VTT"}) == "vtt"


def test_recording_extension_falls_back_from_file_type():
    assert zoom.recording_extension({"file_type": "CHAT"}) == "txt"
    assert zoom.recording_extension({"file_type": "unknown"}) == "bin"


def test_should_download_always_downloads_transcripts():
    assert zoom.should_download({"file_type": "TRANSCRIPT"}, download_recordings=False) is True


def test_should_download_respects_recording_download_flag():
    assert zoom.should_download({"file_type": "MP4"}, download_recordings=False) is False
    assert zoom.should_download({"file_type": "MP4"}, download_recordings=True) is True


def test_render_meeting_markdown_includes_meeting_summary_and_files():
    markdown = zoom.render_meeting_markdown(
        {
            "topic": "Roadmap Review",
            "uuid": "abc123",
            "id": 42,
            "host_email": "host@example.com",
            "start_time": "2026-05-05T08:00:00Z",
            "duration": 30,
            "share_url": "https://example.zoom.us/rec/share/abc123",
            "recording_files": [
                {
                    "file_type": "TRANSCRIPT",
                    "recording_type": "audio_transcript",
                    "status": "completed",
                    "id": "file-1",
                }
            ],
        }
    )

    assert "# Roadmap Review" in markdown
    assert "- Host: host@example.com" in markdown
    assert "- `TRANSCRIPT` audio_transcript (completed) id=`file-1`" in markdown


def test_render_meeting_markdown_notes_when_no_recording_files():
    markdown = zoom.render_meeting_markdown({"topic": "No Files"})

    assert "- No recording files found." in markdown
