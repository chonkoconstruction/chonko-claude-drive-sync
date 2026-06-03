# Claude Trigger Reference
## How Claude updates a Drive doc from within any conversation

This file documents the exact bash_tool calls Claude uses to trigger the
`update-doc.yml` workflow. It is NOT a user-facing doc — it exists so the
mechanism is fully documented in the repo alongside the code it invokes.

---

## Prerequisites (Claude memory)

| Key | Description |
|-----|-------------|
| `GITHUB_PAT` | Fine-grained PAT — Actions (read/write), Contents (read/write), Gist (write) |
| `GITHUB_REPO` | `chonkoconstruction/chonko-claude-drive-sync` |

---

## The Trigger Flow (2 API calls from bash_tool)

### Call 1 — Create a temporary secret Gist

```bash
GIST_ID=$(curl -s -X POST https://api.github.com/gists \
  -H "Authorization: token $GITHUB_PAT" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -d "{
    \"description\": \"chonko-sync: $DOC_NAME\",
    \"public\": false,
    \"files\": {
      \"content.md\": {
        \"content\": $CONTENT_JSON
      }
    }
  }" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Gist created: $GIST_ID"
```

`$CONTENT_JSON` is the document content JSON-encoded (use `jq -Rs .` or Python
`json.dumps()`). The Gist is secret (not public, not indexed).

### Call 2 — Dispatch the GitHub Actions workflow

```bash
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  "https://api.github.com/repos/chonkoconstruction/chonko-claude-drive-sync/actions/workflows/update-doc.yml/dispatches" \
  -H "Authorization: token $GITHUB_PAT" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -d "{
    \"ref\": \"main\",
    \"inputs\": {
      \"file_id\": \"$FILE_ID\",
      \"gist_id\": \"$GIST_ID\",
      \"doc_name\": \"$DOC_NAME\"
    }
  }")

echo "Workflow dispatch status: $HTTP_STATUS"  # expect 204
```

A `204 No Content` response confirms the workflow was queued. The workflow
itself handles Gist cleanup — Claude does NOT need to delete the Gist.

---

## Drive File ID Reference

| Document | Drive File ID |
|----------|--------------|
| DOC-2 SEO Foundational v1.1 | *(add when shared with service)* |
| DOC-3 Titles, Meta & Schema | *(add when shared with service)* |
| DOC-4 Schema JSON-LD | *(add when shared with service)* |

Update this table each time a new Drive doc is connected to the sync system.

---

## GitHub Actions Secrets Required

Set these once in: **repo Settings → Secrets → Actions → New repository secret**

| Secret name | Value |
|-------------|-------|
| `CLAUDE_PAT` | Same PAT stored in Claude memory |
| `APPS_SCRIPT_URL` | The deployed Apps Script web app URL |
| `APPS_SCRIPT_SECRET` | `chonko-drive-claude-sync-2026` |

---

## Architecture Diagram

```
Claude (bash_tool)
    │
    ├─[1]── GitHub API ──► Create secret Gist  (content stored temporarily)
    │                               │
    └─[2]── GitHub API ──► workflow_dispatch ──► GitHub Actions
                                                       │
                                                       ├── Fetch Gist content
                                                       ├── POST to Apps Script webhook
                                                       │       │
                                                       │       └──► Google Drive (file updated in-place)
                                                       └── Delete Gist (cleanup)
```

**Key constraint:** Claude's bash_tool cannot reach Google domains directly.
GitHub Actions can. This workflow is the bridge.
