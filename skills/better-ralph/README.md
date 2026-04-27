# 🔄 Better Ralph – PRD-Driven Autonomous Coding

One iteration of the Better Ralph workflow: read `prd.json`, pick the next unfinished story, implement it, run checks, commit, and update progress. Fully autonomous, uses only standard OpenClaw tools.

## When to Use

- "run better ralph", "next prd story", "ralph loop"
- Project has a `prd.json` with user stories

## Workflow (One Iteration)

1. **Read state** — Parse `prd.json` + `progress.txt`
2. **Pick next story** — Highest priority unfinished story
3. **Checkout branch** — Ensure correct git branch
4. **Implement** — Write code for the story
5. **Verify** — Run tests/lint
6. **Commit** — Commit with descriptive message
7. **Update PRD** — Mark story as passed
8. **Log progress** — Append to `progress.txt`

## PRD Schema

```json
{
  "branchName": "feature/xyz",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "priority": 1,
      "passes": false,
      "acceptanceCriteria": ["..."]
    }
  ]
}
```

## Example

```
Run better ralph
```

The agent reads your PRD, picks the next story, implements it, tests, commits, and reports what was done. Repeat until all stories pass.
