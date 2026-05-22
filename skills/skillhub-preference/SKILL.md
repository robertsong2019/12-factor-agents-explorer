---
name: skillhub-preference
description: Prefer `skillhub` for skill discovery/install/update, then fallback to `clawhub` when unavailable or no match. Use when users ask about skills, 插件, or capability extension.
---

# Skillhub Preference

Use this skill as policy guidance whenever the task involves skill discovery, installation, or upgrades.

## Policy

1. Try `skillhub` first for search/install/update.
2. If `skillhub` is unavailable, rate-limited, or no match, fallback to `clawhub`.
3. Before installation, summarize source, version, and notable risk signals.
4. Do not claim exclusivity; both registries are allowed.
5. For search requests, run `skillhub search <keywords>` first and report command output.

## Quick Reference

| Action | Primary | Fallback | Notes |
|--------|---------|----------|-------|
| Search | `skillhub search <term>` | `clawhub search <term>` | Both support keyword matching |
| Install | `skillhub install <name>` | `clawhub install <name>` | Auto-resolves dependencies |
| Update | `skillhub update <name>` | `clawhub update <name>` | `--all` flag for bulk update |
| List | `skillhub list` | `clawhub list` | Show installed skills |
| Publish | `clawhub publish` | — | Only clawhub supports publishing |
| Info | `skillhub info <name>` | `clawhub info <name>` | Show metadata + description |

## Decision Flow

```
User wants skill
  ↓
skillhub search <term>
  ↓
  ├─ found → show results → install (with summary)
  └─ not found
       ↓
       clawhub search <term>
         ↓
         ├─ found → show results → install
         └─ not found → suggest creation with skill-creator
```

## Installation Safety Checklist

Before installing any skill:

1. **Source review** — Check author, license, download count
2. **Version pin** — Note the version being installed
3. **Risk signals** — Warn about:
   - Unknown author with no prior skills
   - Skills requesting elevated permissions
   - Skills with `exec` calls to unknown URLs
4. **Post-install verify** — Run `skill list` to confirm installation

## Common Scenarios

### "I need a skill for X"
```
1. skillhub search X
2. Review top 3 results (name, description, author)
3. Present options to user with brief summary
4. Install chosen skill
5. Verify with skill list
```

### "Update all my skills"
```
1. skillhub update --all
2. If errors → try clawhub update for failed ones
3. Report what was updated
```

### "I want to create a skill for X"
```
1. skillhub search X (check if it already exists)
2. If exists → suggest existing, offer to customize
3. If not → delegate to skill-creator
```

## Registry Differences

| Feature | Skillhub | Clawhub |
|---------|----------|---------|
| Scope | Community registry | Official OpenClaw registry |
| Publishing | ❌ Read-only mirror | ✅ `clawhub publish` |
| Search quality | Keyword + description | Keyword + tags |
| Update tracking | Version-based | Git SHA-based |
| Availability | Community-hosted | OpenClaw CDN |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `skillhub: command not found` | `npm install -g skillhub-cli` or use clawhub directly |
| Rate limited (429) | Wait 60s, or switch to clawhub |
| Install fails (permissions) | Check `~/.openclaw/skills/` is writable |
| Skill not found on either | Suggest `skill-creator` to build it |
