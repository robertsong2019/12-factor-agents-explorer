# Prompt Template Manager (ptm)

A CLI tool for managing AI prompt templates — store, version, test, and compose prompts.

## Features
- Store prompts with metadata (model, temperature, tags)
- Version history with diff
- Variable interpolation (`{{variable}}`)
- Compose multi-step agent prompts from templates
- Test prompts with dry-run variable substitution
- Import/export JSON bundles

## Usage
```bash
ptm add <name> <template> [tags] [model] [temp]  # Add/update (or pipe template via stdin)
ptm get <name>                # View a template
ptm list [--tag <tag>]        # List templates (filter by tag)
ptm render <name> -k key=val [-k k2=v2 ...]  # Render with variables
ptm compose <t1> <t2> ...    # Compose multiple templates
ptm history <name>            # View version history
ptm diff <name>               # Diff current vs last version
ptm export                    # Export all as JSON
ptm import <file>             # Import from JSON
```

### Pipe mode

```bash
echo "Summarize: {{text}}" | ptm add summarize "summarize,short"
```

With no template argument, `add` reads the template from stdin; remaining
args (`tags model temp`) still work in this order.

### Render semantics

Repeat `-k` for multiple variables — every one is applied, order doesn't
matter. Explicit empty values are supported (`-k note=` → empty string).

## Storage

Templates live as JSON in `~/.ptm/templates/`, version snapshots in
`~/.ptm/versions/`. Override with `PTM_DIR`.

## Testing

```bash
bash test/run.sh   # 29 hermetic tests (isolates PTM_DIR via mktemp)
```

Covers: add/pipe-add arg alignment, `list --tag` filtering, multi-`-k`
render (no dropped vars), compose/export/import round-trip.
