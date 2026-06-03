#!/usr/bin/env python3
"""
scripts/update_drive.py
=======================
Chonko Construction — Drive Sync Worker

Called by the GitHub Actions workflow `update-doc.yml`.
Three-step process:
  1. Read document content from a temp file committed to the repo
  2. POST content to the Chonko Apps Script webhook → Drive file updated in-place
  3. (Temp file deletion handled by the workflow step after this script)

Required environment variables (set as GitHub Actions secrets + workflow inputs):
  APPS_SCRIPT_URL     Deployed Google Apps Script web app URL
  APPS_SCRIPT_SECRET  Apps Script auth secret
  FILE_ID             Google Drive file ID to update
  PENDING_FILE        Repo-relative path to the temp content file

Optional:
  DOC_NAME            Human-readable name for log output (default: "document")
"""

import os
import sys
import requests

TIMEOUT_LONG = 120  # seconds — Drive writes can be slow


def log(msg: str = "") -> None:
    print(msg, flush=True)


def read_content(pending_file: str) -> str:
    """Read the document content from the temp file in the repo checkout."""
    if not os.path.exists(pending_file):
        raise FileNotFoundError(f"Pending content file not found: {pending_file}")
    with open(pending_file, "r", encoding="utf-8") as f:
        content = f.read()
    log(f"  Read {len(content):,} characters from {pending_file}.")
    return content


def update_drive_via_apps_script(
    file_id: str,
    content: str,
    script_url: str,
    secret: str,
) -> None:
    """POST content to the Apps Script webhook to update the Drive file in-place."""
    payload = {
        "secret": secret,
        "action": "update",
        "fileId": file_id,
        "content": content,
    }
    resp = requests.post(script_url, json=payload, timeout=TIMEOUT_LONG)

    if not resp.ok:
        snippet = resp.text[:300] if resp.text else "(no body)"
        raise RuntimeError(f"HTTP {resp.status_code} from Apps Script:\n{snippet}")

    try:
        result = resp.json()
    except Exception:
        log(f"  Apps Script responded (non-JSON, HTTP 200): {resp.text[:200]}")
        return

    if "error" in result:
        raise RuntimeError(f"Apps Script returned an error: {result['error']}")

    log(f"  Drive file {file_id} updated. Response: {result}")


def main() -> None:
    try:
        script_url   = os.environ["APPS_SCRIPT_URL"]
        secret       = os.environ["APPS_SCRIPT_SECRET"]
        file_id      = os.environ["FILE_ID"]
        pending_file = os.environ["PENDING_FILE"]
    except KeyError as e:
        sys.exit(f"ERROR: Missing required environment variable: {e}")

    doc_name = os.environ.get("DOC_NAME", "document")

    log("=== Chonko Drive Sync ===")
    log(f"Target : '{doc_name}'")
    log(f"File ID: {file_id}")
    log(f"Source : {pending_file}")
    log()

    log("[1/2] Reading content from repo temp file…")
    content = read_content(pending_file)

    log("[2/2] Pushing content to Google Drive…")
    update_drive_via_apps_script(file_id, content, script_url, secret)

    log()
    log("✅ Done. (Temp file will be cleaned up by the workflow.)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"ERROR: {e}")
