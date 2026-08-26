# prompt-template-manager (ptm)

Store, catalog, and render prompt templates with `{{variable}}` substitution.

## Commands

```bash
ptm list                          # List all templates
ptm show <name>                   # Display a template
ptm add <name> [content]          # Add new template (reads stdin if no content)
                                  #   refuses to overwrite without --force
ptm add <name> --force [content]  # Overwrite an existing template
echo "Hello {{who}}" | ptm add hello  # stdin form — pipe-friendly
ptm edit <name>                   # Open template in $EDITOR / $VISUAL
ptm render <name> key=val ...     # Render with variables
ptm export <name> key=val ...     # Output rendered (pipe-friendly)
```

### Variable semantics

Explicit empty values are honored: `k=` renders as an empty string,
not as a leftover `{{k}}`. Only *missing* keys are left unsubstituted.

### Name validation

Template names must match `[\w][\w.-]*` (letters, digits, `_`, `.`, `-`;
no path separators) on every name-taking command (`add`/`show`/`render`/
`export`/`edit`). This guards the write path against crashes (`a/b` used to
throw a raw ENOENT stack trace) and read joins against `../` traversal out
of the templates directory.

### Editor semantics (`edit`)

`$EDITOR` takes precedence over `$VISUAL`; both may contain arguments
(`EDITOR="code --wait"` works). The editor runs with inherited stdio — fully
interactive — and its exit code is propagated.

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
npm test   # 29 hermetic tests (isolates HOME/templates via mktemp)
```

Covers: stdin add, explicit-empty render, list/show/export, missing-template
errors, overwrite refusal + `--force`, name validation (separators, traversal,
empty), `edit` (EDITOR/VISUAL resolution, no-editor error). All three current
guard behaviors were red-verified on the unfixed code before fixing (6-fail
baseline), not written after the fact.
