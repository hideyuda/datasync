import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List

import pytz
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def build_calendar_client():
    client_id = env("GCAL_CLIENT_ID")
    client_secret = env("GCAL_CLIENT_SECRET")
    refresh_token = env("GCAL_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        print("GCal: missing secrets, skipping.")
        return None
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def write_daily_markdown(day: datetime, events: List[Dict]) -> None:
    ensure_dir(os.path.join("data", "calendar"))
    path = os.path.join("data", "calendar", day.strftime("%Y-%m-%d") + ".md")
    lines = [f"# {day.strftime('%Y-%m-%d')}"]
    events_sorted = sorted(events, key=lambda e: e.get("start_dt") or "")
    for e in events_sorted:
        start = e.get("start_dt_display", "")
        end = e.get("end_dt_display", "")
        line = f"- {start}–{end} {e.get('summary', '(no title)')}"
        if "location" in e and e["location"]:
            line += f" @ {e['location']}"
        lines.append(line)
        desc = e.get("description")
        if desc:
            lines.append(f"  \n  {desc.strip()}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def parse_event_dates(event: Dict, tz: pytz.BaseTzInfo) -> Dict:
    # Handles all-day and timed events
    start = event.get("start", {})
    end = event.get("end", {})
    if "dateTime" in start:
        sdt = datetime.fromisoformat(
            start["dateTime"].replace("Z", "+00:00")
        ).astimezone(tz)
        edt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00")).astimezone(
            tz
        )
        event["start_dt"] = sdt.isoformat()
        event["end_dt"] = edt.isoformat()
        event["start_dt_display"] = sdt.strftime("%H:%M")
        event["end_dt_display"] = edt.strftime("%H:%M")
    else:
        sdt = datetime.fromisoformat(start["date"] + "T00:00:00").astimezone(tz)
        edt = datetime.fromisoformat(end["date"] + "T00:00:00").astimezone(tz)
        event["start_dt"] = sdt.isoformat()
        event["end_dt"] = edt.isoformat()
        event["start_dt_display"] = "All-day"
        event["end_dt_display"] = ""
    return event


def sync() -> None:
    cal = build_calendar_client()
    if cal is None:
        return

    calendar_id = env("GCAL_CALENDAR_ID", "primary")
    tz = pytz.timezone("UTC")
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=90)).isoformat()
    end = (now + timedelta(days=90)).isoformat()

    events: List[Dict] = []
    page_token = None
    while True:
        resp = (
            cal.events()
            .list(
                calendarId=calendar_id,
                singleEvents=True,
                orderBy="startTime",
                timeMin=start,
                timeMax=end,
                pageToken=page_token,
                maxResults=2500,
            )
            .execute()
        )
        for e in resp.get("items", []):
            e = parse_event_dates(e, tz)
            events.append(
                {
                    "id": e.get("id"),
                    "summary": e.get("summary"),
                    "description": e.get("description"),
                    "location": e.get("location"),
                    "start_dt": e.get("start_dt"),
                    "end_dt": e.get("end_dt"),
                }
            )
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # partition by date
    buckets: Dict[str, List[Dict]] = {}
    for e in events:
        day = e["start_dt"][:10]
        buckets.setdefault(day, []).append(e)

    for day_str, day_events in buckets.items():
        day = datetime.fromisoformat(day_str + "T00:00:00+00:00")
        write_daily_markdown(day, day_events)

    ensure_dir("data")
    with open(os.path.join("data", "state.json"), "w") as f:
        json.dump(
            {"last_run": datetime.now(timezone.utc).isoformat(), "events": len(events)},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Wrote {len(events)} events into daily Markdown files")


if __name__ == "__main__":
    sync()
