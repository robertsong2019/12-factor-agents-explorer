#!/usr/bin/env node
// prompt-template-manager (ptm) — Store, catalog, and render prompt templates
// Usage: ptm <command> [options]
//
// Commands:
//   list                    List all templates
//   show <name>             Show a template
//   add <name>              Add template from stdin or clipboard
//   render <name> [k=v...]  Render template with variables
//   edit <name>             Open template in $EDITOR
//   export <name>           Output rendered prompt to stdout (for piping)

import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { spawnSync } from 'child_process';

const HOME = process.env.HOME || '/root';
const TEMPLATES_DIR = join(HOME, '.openclaw/workspace/tools/prompt-template-manager/templates');

if (!existsSync(TEMPLATES_DIR)) mkdirSync(TEMPLATES_DIR, { recursive: true });

const args = process.argv.slice(2);
const command = args[0];

function getTemplates() {
  return readdirSync(TEMPLATES_DIR)
    .filter(f => f.endsWith('.md'))
    .map(f => {
      const content = readFileSync(join(TEMPLATES_DIR, f), 'utf-8');
      const firstLine = content.split('\n')[0] || '';
      const desc = firstLine.startsWith('#') ? firstLine.replace(/^#+\s*/, '') : '(no description)';
      return { name: f.replace(/\.md$/, ''), file: f, desc, size: content.length };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

function render(content, vars) {
  // hasOwn check: an explicitly-passed empty value (k=) must substitute as '',
  // only truly-absent keys stay visible as {{key}}
  return content.replace(/\{\{(\w+)\}\}/g, (_, key) => (Object.hasOwn(vars, key) ? vars[key] : `{{${key}}}`));
}

function parseVars(args) {
  const vars = {};
  for (const a of args) {
    const eq = a.indexOf('=');
    if (eq > 0) vars[a.slice(0, eq)] = a.slice(eq + 1);
  }
  return vars;
}

// Guards the write path (and read joins) against path separators/traversal:
// "a/b" would crash writeFileSync with ENOENT; "../x" escapes TEMPLATES_DIR.
function validateName(name) {
  if (!name || !/^[\w][\w.-]*$/.test(name)) {
    console.error(`Invalid template name: ${JSON.stringify(name)} (allowed: letters, digits, _, ., -)`);
    process.exit(1);
  }
  return name;
}

switch (command) {
  case 'list':
  case 'ls': {
    const templates = getTemplates();
    if (!templates.length) { console.log('No templates found. Use `ptm add <name>` to create one.'); break; }
    console.log('📝 Prompt Templates\n');
    for (const t of templates) {
      console.log(`  ${t.name.padEnd(25)} ${t.desc.slice(0, 50)}`);
    }
    console.log(`\n${templates.length} templates`);
    break;
  }
  case 'show': {
    if (!args[1]) { console.error('Usage: ptm show <name>'); process.exit(1); }
    const name = validateName(args[1]);
    const p = join(TEMPLATES_DIR, name + '.md');
    if (!existsSync(p)) { console.error(`Template not found: ${name}`); process.exit(1); }
    console.log(readFileSync(p, 'utf-8'));
    break;
  }
  case 'add': {
    if (!args[1]) { console.error('Usage: ptm add <name> [content]'); process.exit(1); }
    const name = validateName(args[1]);
    const rest = args.slice(2);
    const force = rest.includes('--force');
    const content = rest.filter(a => a !== '--force').join(' ') || (() => {
      // Read from stdin if no content provided
      console.error('Enter template content (Ctrl+D to finish):');
      // fd 0, not '/dev/stdin': the path form throws ENXIO when stdin is a pipe
      // in some spawn contexts (e.g. child_process input option)
      return readFileSync(0, 'utf-8');
    })();
    const dest = join(TEMPLATES_DIR, name + '.md');
    if (existsSync(dest) && !force) {
      console.error(`Template already exists: ${name} (use --force to overwrite)`);
      process.exit(1);
    }
    writeFileSync(dest, content, 'utf-8');
    console.log(`✅ Added template: ${name}`);
    break;
  }
  case 'edit': {
    if (!args[1]) { console.error('Usage: ptm edit <name>'); process.exit(1); }
    const name = validateName(args[1]);
    const p = join(TEMPLATES_DIR, name + '.md');
    if (!existsSync(p)) { console.error(`Template not found: ${name}`); process.exit(1); }
    const editor = process.env.EDITOR || process.env.VISUAL;
    if (!editor) { console.error('No editor configured: set $EDITOR or $VISUAL'); process.exit(1); }
    // Split so "code --wait" style editors work; stdio inherit keeps the editor interactive
    const parts = editor.split(/\s+/);
    const r = spawnSync(parts[0], [...parts.slice(1), p], { stdio: 'inherit' });
    if (r.error) { console.error(`Failed to launch editor: ${r.error.message}`); process.exit(1); }
    process.exit(r.status ?? 0);
    break;
  }
  case 'render': {
    if (!args[1]) { console.error('Usage: ptm render <name> [key=value ...]'); process.exit(1); }
    const name = validateName(args[1]);
    const p = join(TEMPLATES_DIR, name + '.md');
    if (!existsSync(p)) { console.error(`Template not found: ${name}`); process.exit(1); }
    const vars = parseVars(args.slice(2));
    const result = render(readFileSync(p, 'utf-8'), vars);
    console.log(result);
    break;
  }
  case 'export': {
    if (!args[1]) { console.error('Usage: ptm export <name> [key=value ...]'); process.exit(1); }
    const name = validateName(args[1]);
    const p = join(TEMPLATES_DIR, name + '.md');
    if (!existsSync(p)) { console.error(`Template not found: ${name}`); process.exit(1); }
    const vars = parseVars(args.slice(2));
    process.stdout.write(render(readFileSync(p, 'utf-8'), vars));
    break;
  }
  default:
    console.log(`prompt-template-manager (ptm) v1.0.0
Store, catalog, and render prompt templates with variable substitution.

Usage: ptm <command> [options]

Commands:
  list                    List all templates
  show <name>             Display a template
  add <name> [content]    Add new template (reads stdin if no content)
  edit <name>             Open template in $EDITOR
  render <name> [k=v...]  Render template with variables
  export <name> [k=v...]  Output rendered prompt (no extra formatting)

Templates use {{variable}} syntax for substitution.
Template directory: ${TEMPLATES_DIR}
`);
}
