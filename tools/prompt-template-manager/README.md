# prompt-template-manager (ptm)

Store, catalog, and render prompt templates with `{{variable}}` substitution.

## Commands

```bash
ptm list                          # List all templates
ptm show <name>                   # Display a template
ptm add <name> [content]          # Add new template (reads stdin if no content)
echo "Hello {{who}}" | ptm add hello  # stdin form — pipe-friendly
ptm render <name> key=val ...     # Render with variables
ptm export <name> key=val ...     # Output rendered (pipe-friendly)
```

### Variable semantics

Explicit empty values are honored: `k=` renders as an empty string,
not as a leftover `{{k}}`. Only *missing* keys are left unsubstituted.

## Bundled Templates

- **code-review** — Structured code review prompt
- **bug-investigation** — Root cause analysis prompt  
- **skill-design** — OpenClaw skill design prompt

## Add Your Own

Drop `.md` files into `templates/` with `{{variable}}` placeholders:

```markdown
# Analyze {{type}}
Examine this {{type}} for {{goal}}:
{{content}}
```

Then: `ptm render analyze type=API goal="security issues" content="..."`

## Design

- Zero dependencies
- Templates are plain Markdown — version control friendly
- `export` outputs raw text for piping to other tools
- stdin is read via fd 0 directly — `ptm add name` works inside pipes

## Testing

```bash
npm test   # 20 hermetic tests (isolates HOME/templates via mktemp)
```

Covers: stdin add, explicit-empty render, list/show/export, missing-template
errors.
