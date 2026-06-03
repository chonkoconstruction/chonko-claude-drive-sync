#!/usr/bin/env python3
"""
scripts/update_drive.py — Chonko Drive Sync Worker

Uses Google Docs API batchUpdate to:
1. Fix page size back to US Letter (8.5" x 11") with standard margins
2. Replace all document content with new markdown text
3. Apply H1/H2/H3 heading styles to lines starting with #/##/###
"""
import os, sys, json
from google.oauth2 import service_account
from googleapiclient.discovery import build

def log(msg=""): print(msg, flush=True)

def build_requests(new_text, end_index):
    reqs = []

    # 1. Delete existing content
    if end_index > 1:
        reqs.append({"deleteContentRange": {
            "range": {"startIndex": 1, "endIndex": end_index}
        }})

    # 2. Reset page to US Letter portrait with 1-inch margins
    reqs.append({"updateDocumentStyle": {
        "documentStyle": {
            "pageSize": {
                "height": {"magnitude": 792, "unit": "PT"},
                "width":  {"magnitude": 612, "unit": "PT"}
            },
            "marginTop":    {"magnitude": 72, "unit": "PT"},
            "marginBottom": {"magnitude": 72, "unit": "PT"},
            "marginLeft":   {"magnitude": 72, "unit": "PT"},
            "marginRight":  {"magnitude": 72, "unit": "PT"},
        },
        "fields": "pageSize,marginTop,marginBottom,marginLeft,marginRight"
    }})

    # 3. Insert new text
    reqs.append({"insertText": {
        "location": {"index": 1},
        "text": new_text
    }})

    # 4. Apply heading styles line by line
    idx = 1
    for line in new_text.split("\n"):
        line_len = len(line) + 1  # +1 for the \n
        stripped = line.lstrip()
        end = idx + line_len

        if stripped.startswith("### "):
            style = "HEADING_3"
        elif stripped.startswith("## "):
            style = "HEADING_2"
        elif stripped.startswith("# "):
            style = "HEADING_1"
        else:
            idx += line_len
            continue

        reqs.append({"updateParagraphStyle": {
            "range": {"startIndex": idx, "endIndex": end},
            "paragraphStyle": {"namedStyleType": style},
            "fields": "namedStyleType"
        }})
        idx += line_len

    return reqs

def main():
    try:
        sa_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        file_id = os.environ["FILE_ID"]
        pf      = os.environ["PENDING_FILE"]
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

    doc = docs.documents().get(documentId=file_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1
    log(f"Current doc end index: {end_index}")

    reqs = build_requests(new_text, end_index)
    heading_count = sum(1 for r in reqs if "updateParagraphStyle" in r)
    log(f"Requests: {len(reqs)} total ({heading_count} heading styles)")

    docs.documents().batchUpdate(
        documentId=file_id,
        body={"requests": reqs}
    ).execute()

    log("✅ Done — content replaced, page reset, headings styled.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"ERROR: {e}")
