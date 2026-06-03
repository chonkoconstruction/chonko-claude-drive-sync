#!/usr/bin/env python3
"""
scripts/update_drive.py — Chonko Drive Sync Worker
Updates a Google Drive file directly via the Drive API using a service account.
"""
import os, sys, json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

def log(msg=""): print(msg, flush=True)

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

    # Read content
    with open(pf, "r", encoding="utf-8") as f:
        content = f.read()
    log(f"Content: {len(content):,} chars — first line: {content.splitlines()[0]}")

    # Auth
    sa_info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )

    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    # Update file content
    log("\nUpdating Drive file…")
    media = MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/plain")
    result = service.files().update(fileId=file_id, media_body=media).execute()

    log(f"✅ Updated: {result.get('name')} ({result.get('id')})")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"ERROR: {e}")
