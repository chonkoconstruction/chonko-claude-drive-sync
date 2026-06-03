#!/usr/bin/env python3
"""
scripts/update_drive.py — Chonko Drive Sync Worker

Uses the Google Docs API batchUpdate to replace document content in-place.
This preserves page size, margins, headers/footers, and all layout settings.
Only the body text is replaced.
"""
import os, sys, json
from google.oauth2 import service_account
from googleapiclient.discovery import build

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

    with open(pf, "r", encoding="utf-8") as f:
        new_text = f.read()
    log(f"Content: {len(new_text):,} chars — first line: {new_text.splitlines()[0]}")

    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json),
        scopes=["https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive"]
    )

    docs = build("docs", "v1", credentials=creds, cache_discovery=False)

    # Get current document to find the content end index
    log("\nReading current document structure…")
    doc = docs.documents().get(documentId=file_id).execute()
    body_content = doc["body"]["content"]
    end_index = body_content[-1]["endIndex"] - 1  # -1 to preserve final newline

    log(f"Current end index: {end_index}")

    # Build batchUpdate: delete all content, then insert new text
    requests = []
    if end_index > 1:
        requests.append({
            "deleteContentRange": {
                "range": {"startIndex": 1, "endIndex": end_index}
            }
        })
    requests.append({
        "insertText": {
            "location": {"index": 1},
            "text": new_text
        }
    })

    log("Applying updates…")
    docs.documents().batchUpdate(
        documentId=file_id,
        body={"requests": requests}
    ).execute()

    log(f"✅ Done — content replaced, page layout preserved.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"ERROR: {e}")
