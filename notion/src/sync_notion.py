import os
import json
from notion_client import Client
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def env(name: str, default: str = None) -> str:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_markdown(path: str, title: str, properties: Dict, url: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"URL: {url}\n\n")
        f.write("## Properties\n\n")
        for key, value in properties.items():
            f.write(f"- **{key}**: {value}\n")


def get_title(page: Dict) -> str:
    props = page.get("properties", {})
    for key, val in props.items():
        if val.get("type") == "title":
            title_list = val.get("title", [])
            if title_list:
                return "".join([t.get("plain_text", "") for t in title_list])
    return "Untitled"


def sync():
    notion_token = env("NOTION_API_KEY")
    if not notion_token:
        print("Notion: NOTION_API_KEY not found, skipping.")
        return

    client = Client(auth=notion_token)

    print("Notion: Searching for pages...")
    # Search for all pages and databases
    results = []
    has_more = True
    start_cursor = None

    while has_more:
        response = client.search(start_cursor=start_cursor)
        results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    print(f"Notion: Found {len(results)} items.")

    ensure_dir(os.path.join("data", "pages"))
    ensure_dir(os.path.join("data", "databases"))

    for item in results:
        obj_type = item.get("object")
        item_id = item.get("id")
        # last_edited = item.get("last_edited_time")
        url = item.get("url")

        if obj_type == "page":
            title = get_title(item)
            safe_title = "".join(
                [c for c in title if c.isalnum() or c in (" ", "-", "_")]
            ).strip()
            if not safe_title:
                safe_title = item_id

            filename = f"{safe_title}_{item_id}.json"
            md_filename = f"{safe_title}_{item_id}.md"

            # Save raw JSON
            save_json(os.path.join("data", "pages", filename), item)

            # Save simple Markdown
            # Note: This doesn't fetch page content (blocks), just properties for now to keep it simple and fast.
            # Fetching blocks would require recursive calls.
            save_markdown(
                os.path.join("data", "pages", md_filename),
                title,
                item.get("properties", {}),
                url,
            )

        elif obj_type == "database":
            title_list = item.get("title", [])
            title = (
                "".join([t.get("plain_text", "") for t in title_list])
                if title_list
                else "Untitled"
            )
            safe_title = "".join(
                [c for c in title if c.isalnum() or c in (" ", "-", "_")]
            ).strip()
            if not safe_title:
                safe_title = item_id

            filename = f"{safe_title}_{item_id}.json"
            save_json(os.path.join("data", "databases", filename), item)

    print("Notion: Sync complete.")


if __name__ == "__main__":
    sync()
