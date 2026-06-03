#!/usr/bin/env python3
"""
scripts/update_drive.py — Chonko Drive Sync Worker
Reads content from a repo temp file, POSTs to Apps Script webhook,
and handles Google's POST-preserving redirect chain.
"""
import os, sys, json, requests

TIMEOUT = 60

def log(msg=""): print(msg, flush=True)

def post_with_redirects(url, payload, timeout=TIMEOUT):
    """POST to Apps Script, preserving POST method through Google's redirects."""
    session = requests.Session()
    resp = session.post(url, json=payload, allow_redirects=False, timeout=timeout)
    hops = 0
    while resp.status_code in (301, 302, 303, 307, 308) and hops < 6:
        location = resp.headers.get("Location", "")
        log(f"  Redirect {resp.status_code} → {location[:80]}")
        resp = session.post(location, json=payload, allow_redirects=False, timeout=timeout)
        hops += 1
    return resp

def main():
    try:
        url    = os.environ["APPS_SCRIPT_URL"]
        secret = os.environ["APPS_SCRIPT_SECRET"]
        fid    = os.environ["FILE_ID"]
        pf     = os.environ["PENDING_FILE"]
    except KeyError as e:
        sys.exit(f"Missing env var: {e}")

    doc_name = os.environ.get("DOC_NAME", "document")

    log("=== Chonko Drive Sync ===")
    log(f"Target : {doc_name}")
    log(f"File ID: {fid}")

    with open(pf, "r", encoding="utf-8") as f:
        content = f.read()
    log(f"Content: {len(content):,} chars — first line: {content.splitlines()[0]}")

    log("\nCalling Apps Script…")
    payload = {"secret": secret, "action": "update", "fileId": fid, "content": content}
    resp = post_with_redirects(url, payload)

    log(f"Final status : {resp.status_code}")
    log(f"Response     : {resp.text[:400]}")

    if not resp.ok:
        sys.exit(f"ERROR: HTTP {resp.status_code}")

    try:
        result = resp.json()
        if "error" in result:
            sys.exit(f"ERROR from Apps Script: {result['error']}")
    except Exception:
        pass  # non-JSON 200 is fine

    log("\n✅ Done.")

if __name__ == "__main__":
    main()
