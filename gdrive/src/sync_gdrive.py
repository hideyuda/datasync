import csv
import io
import json
import os
from typing import Optional

import html2text
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def build_drive_client():
    client_id = env("GDRIVE_CLIENT_ID")
    client_secret = env("GDRIVE_CLIENT_SECRET")
    refresh_token = env("GDRIVE_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        print("GDrive: missing secrets, skipping.")
        return None
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def safe_name(name: str) -> str:
    bad = '<>:"/\\|?*'
    out = name
    for c in bad:
        out = out.replace(c, "_")
    return out.strip()


def csv_to_markdown(csv_bytes: bytes) -> str:
    text = csv_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return ""
    # simple markdown table
    header = rows[0]
    lines = []
    lines.append("| " + " | ".join(h if h is not None else "" for h in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def export_file_to_markdown(
    drive, file_id: str, name: str, mime_type: str
) -> Optional[str]:
    # Google Docs
    if mime_type == "application/vnd.google-apps.document":
        try:
            data = drive.files().export(fileId=file_id, mimeType="text/html").execute()
            md = html2text.HTML2Text()
            md.ignore_images = False
            md.ignore_links = False
            return md.handle(data.decode("utf-8", errors="replace"))
        except HttpError as e:
            print(f"Export error (Docs) {name}: {e}")
            return None
    # Google Slides
    if mime_type == "application/vnd.google-apps.presentation":
        try:
            data = drive.files().export(fileId=file_id, mimeType="text/html").execute()
            md = html2text.HTML2Text()
            md.ignore_images = False
            md.ignore_links = False
            return md.handle(data.decode("utf-8", errors="replace"))
        except HttpError as e:
            print(f"Export error (Slides) {name}: {e}")
            return None
    # Google Sheets (first sheet CSV -> MD table)
    if mime_type == "application/vnd.google-apps.spreadsheet":
        try:
            data = drive.files().export(fileId=file_id, mimeType="text/csv").execute()
            return csv_to_markdown(data)
        except HttpError as e:
            print(f"Export error (Sheets) {name}: {e}")
            return None
    # unsupported types (skip)
    return None


def save_markdown(name: str, file_id: str, content: str) -> None:
    ensure_dir("data/md")
    safe = safe_name(name)
    path = os.path.join("data", "md", f"{safe}_{file_id}.md")
    with open(path, "w") as f:
        f.write(content)


def sync() -> None:
    drive = build_drive_client()
    if drive is None:
        return
    q = env("GDRIVE_ROOT_QUERY", "trashed = false")

    page_token = None
    total = 0
    while True:
        try:
            resp = (
                drive.files()
                .list(
                    q=q,
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                    pageToken=page_token,
                    pageSize=200,
                )
                .execute()
            )
        except HttpError as e:
            print(f"List error: {e}")
            break
        for fmeta in resp.get("files", []):
            fid = fmeta["id"]
            name = fmeta["name"]
            mime = fmeta["mimeType"]
            md = export_file_to_markdown(drive, fid, name, mime)
            if md is not None:
                save_markdown(name, fid, md)
                total += 1
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    ensure_dir("data")
    with open(os.path.join("data", "state.json"), "w") as f:
        json.dump(
            {"last_run": True, "exported": total}, f, ensure_ascii=False, indent=2
        )
    print(f"Exported {total} file(s) to Markdown")


if __name__ == "__main__":
    sync()
