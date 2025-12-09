# Google Calendar Sync (±3 months)

Exports events from the past 3 months to the next 3 months into daily Markdown files.

Output:
- `data/calendar/YYYY-MM-DD.md` daily agendas
- `data/state.json` last run time

Secrets:
- `GCAL_CLIENT_ID`
- `GCAL_CLIENT_SECRET`
- `GCAL_REFRESH_TOKEN`

Variables:
- `GCAL_CALENDAR_ID` optional; defaults to `"primary"`


