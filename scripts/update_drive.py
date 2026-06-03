#!/usr/bin/env python3
"""
scripts/update_drive.py
=======================
Chonko Construction — Drive Sync Worker

Called by the GitHub Actions workflow `update-doc.yml`.
Three-step process:
  1. Fetch document content from a temporary GitHub Gist
  2. POST content to the Chonko Apps Script webhook → Drive file updated in-place
  3. Delete the Gist (cleanup)

Required environment variables (set as GitHub Actions secrets):
  CLAUDE_PAT        Fine-grained GitHub PAT with 'gist' scope
  APPS_SCRIPT_URL   Deployed Google Apps Script web app URL
  APPS_SCRIPT_SECRET Apps Script auth secret
  FILE_ID           Google Drive file ID to update
  GIST_ID           GitHub Gist ID containing the new content

Optional:
  DOC_NAME          Human-readable name for log output (default: "document")
"""

import os
import sys
import requests

GITHUB_API = "https://api.github.com"
TIMEOUT_SHORT = 30   # seconds — for Gist fetch/delete
TIMEOUT_LONG  = 120  # seconds — for Apps Script (Drive writes can be slow)


# ── Logging ────────────────────────────────────────────────────────────────────

def log(msg: str = "") -> None:
    print(msg, flush=True)


# ── Step 1: Fetch Gist content ─────────────────────────────────────────────────

def fetch_gist_content(gist_id: str, token: str) -> str:
    """Return the content of the first file in a GitHub Gist."""
    url = f"{GITHUB_API}/gists/{gist_id}"
    headers = _gh_headers(token)

    resp = requests.get(url, headers=headers, timeout=TIMEOUT_SHORT)
    _raise_for_status(resp, "fetch Gist")

    files = resp.json().get("files", {})
    if not files:
        raise ValueError(f"Gist {gist_id} contains no files.")

    first_file = next(iter(files.values()))
    content = first_file.get("content", "")

    # Gist API truncates files > 1 MB — fall back to raw_url
    if not content and first_file.get("truncated"):
        log("  Content truncated — fetching via raw_url…")
        raw_resp = requests.get(
            first_file["raw_url"],
            headers=headers,
            timeout=60,
        )
        _raise_for_status(raw_resp, "fetch raw Gist content")
        content = raw_resp.text

    log(f"  Fetched {len(content):,} characters from Gist {gist_id}.")
    return content


# ── Step 2: Update Drive via Apps Script ───────────────────────────────────────

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
    _raise_for_status(resp, "call Apps Script webhook")

    # Gracefully handle varying response shapes from the Apps Script
    try:
        result = resp.json()
    except Exception:
        # Non-JSON but HTTP 200 — treat as success, log raw text for visibility
        log(f"  Apps Script responded (non-JSON, HTTP 200): {resp.text[:200]}")
        return

    # Flag explicit error fields if present
    if "error" in result:
        raise RuntimeError(f"Apps Script returned an error: {result['error']}")

    log(f"  Drive file {file_id} updated. Response: {result}")


# ── Step 3: Delete Gist ────────────────────────────────────────────────────────

def delete_gist(gist_id: str, token: str) -> None:
    """Delete the temporary Gist after the Drive update succeeds."""
    url = f"{GITHUB_API}/gists/{gist_id}"
    resp = requests.delete(url, headers=_gh_headers(token), timeout=TIMEOUT_SHORT)

    if resp.status_code == 204:
        log(f"  Gist {gist_id} deleted.")
    else:
        # Non-fatal — log a warning but don't fail the workflow
        log(f"  Warning: Gist deletion returned HTTP {resp.status_code} (may already be gone).")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _raise_for_status(resp: requests.Response, context: str) -> None:
    if not resp.ok:
        snippet = resp.text[:300] if resp.text else "(no body)"
        raise RuntimeError(
            f"HTTP {resp.status_code} while trying to {context}:\n{snippet}"
        )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    # Read all config from environment (set by GitHub Actions secrets + workflow inputs)
    try:
        claude_pat   = os.environ["CLAUDE_PAT"]
        script_url   = os.environ["APPS_SCRIPT_URL"]
        secret       = os.environ["APPS_SCRIPT_SECRET"]
        file_id      = os.environ["FILE_ID"]
        gist_id      = os.environ["GIST_ID"]
    except KeyError as e:
        sys.exit(f"ERROR: Missing required environment variable: {e}")

    doc_name = os.environ.get("DOC_NAME", "document")

    log("=== Chonko Drive Sync ===")
    log(f"Target : '{doc_name}'")
    log(f"File ID: {file_id}")
    log(f"Gist ID: {gist_id}")
    log()

    log("[1/3] Fetching content from Gist…")
    content = fetch_gist_content(gist_id, claude_pat)

    log("[2/3] Pushing content to Google Drive…")
    update_drive_via_apps_script(file_id, content, script_url, secret)

    log("[3/3] Cleaning up temporary Gist…")
    delete_gist(gist_id, claude_pat)

    log()
    log("✅ Done.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except requests.HTTPError as e:
        body = e.response.text[:300] if e.response else ""
        sys.exit(f"ERROR: HTTP {e.response.status_code} — {body}")
    except Exception as e:
        sys.exit(f"ERROR: {e}")
