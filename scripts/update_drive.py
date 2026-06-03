#!/usr/bin/env python3
"""
scripts/update_drive.py — Chonko Drive Sync Worker
Converts markdown to HTML and updates a Google Drive file via service account.
Uploading as HTML preserves heading hierarchy, bold, tables, and lists.
"""
import os, sys, json
import markdown as md_lib
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

def log(msg=""): print(msg, flush=True)

def md_to_html(content: str) -> str:
    """Convert markdown to HTML with tables and fenced code support."""
    html_body = md_lib.markdown(content, extensions=["tables", "fenced_code", "nl2br"])
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; }}
  h1 {{ font-size: 24px; }} h2 {{ font-size: 20px; }} h3 {{ font-size: 16px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ border: 1px solid #ccc; padding: 6px 10px; }}
  code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
</style>
</head><body>{html_body}</body></html>"""

def main():
    try:
        sa_json  = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        file_id  = os.environ["FILE_ID"]
        pf       = os.environ["PENDING_FILE"]
    except KeyError as e:
        sys.exit(f"Missing env var: {e}")

    doc_name = os.environ.get("DOC_NAME", "document")

    log("=== Chonko Drive Sync ===")
    log(f"Target : {doc_name}")
    log(f"File ID: {file_id}")

    with open(pf, "r", encoding="utf-8") as f:
        content = f.read()
    log(f"Content: {len(content):,} chars — first line: {content.splitlines()[0]}")

    html = md_to_html(content)
    log(f"HTML   : {len(html):,} chars")

    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json),
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    log("\nUpdating Drive file…")
    media = MediaInMemoryUpload(html.encode("utf-8"), mimetype="text/html")
    result = service.files().update(fileId=file_id, media_body=media).execute()
    log(f"✅ Updated: {result.get('name')} ({result.get('id')})")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"ERROR: {e}")
