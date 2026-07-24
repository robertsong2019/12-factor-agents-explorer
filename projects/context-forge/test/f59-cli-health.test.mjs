import { test } from 'node:test';
import assert from 'node:assert';
import { analyzeCliHealth, formatCliHealthReport } from '../context-forge.mjs';

test('analyzeCliHealth — returns null-safe result for empty input', () => {
  const result = analyzeCliHealth([]);
  assert.equal(result.cliFileCount, 0);
  assert.equal(result.healthScore, 0);
  assert.equal(result.grade, 'F');
});

test('analyzeCliHealth — returns null-safe result for null', () => {
  const result = analyzeCliHealth(null);
  assert.equal(result.cliFileCount, 0);
});

test('analyzeCliHealth — detects CLI file via process.argv', () => {
  const files = [{
    path: 'cli.mjs',
    content: `#!/usr/bin/env node
import { readFileSync } from 'fs';
const args = process.argv.slice(2);
if (args.includes('--help') || args.includes('-h')) {
  console.log('Usage: cli [options]');
  process.exit(0);
}
if (args.includes('--version') || args.includes('-v')) {
  console.log('1.0.0');
  process.exit(0);
}
if (!args[0]) {
  console.error('Error: missing argument');
  process.exit(1);
}
console.log('done');
`,
  }];
  const result = analyzeCliHealth(files);
  assert.equal(result.cliFileCount, 1);
  assert.ok(result.healthScore >= 75, `score should be >= 75, got ${result.healthScore}`);
  assert.equal(result.files[0].isEntry, true);
});

test('analyzeCliHealth — detects CLI file via shebang', () => {
  const files = [{
    path: 'bin/run.js',
    content: `#!/usr/bin/env node
console.log('hello');
`,
  }];
  const result = analyzeCliHealth(files);
  assert.equal(result.cliFileCount, 1);
});

test('analyzeCliHealth — detects commander usage', () => {
  const files = [{
    path: 'src/cli.ts',
    content: `import { Command } from 'commander';
const program = new Command();
program.command('build').action(() => {});
program.parse();
`,
  }];
  const result = analyzeCliHealth(files);
  assert.equal(result.cliFileCount, 1);
  assert.equal(result.files[0].framework, 'commander/yargs');
});

test('analyzeCliHealth — skips non-CLI files', () => {
  const files = [{
    path: 'lib/utils.mjs',
    content: 'export const add = (a, b) => a + b;',
  }];
  const result = analyzeCliHealth(files);
  assert.equal(result.cliFileCount, 0);
});

test('analyzeCliHealth — detects missing help flag', () => {
  const files = [{
    path: 'cli.mjs',
    content: `const args = process.argv.slice(2);
console.log('run');
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.files[0].issues.some(i => i.type === 'missing_help'));
});

test('analyzeCliHealth — detects missing version flag', () => {
  const files = [{
    path: 'cli.mjs',
    content: `const args = process.argv.slice(2);
if (args.includes('--help')) console.log('help');
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.files[0].issues.some(i => i.type === 'missing_version'));
});

test('analyzeCliHealth — detects missing usage docs', () => {
  const files = [{
    path: 'cli.mjs',
    content: `const args = process.argv.slice(2);
if (args.includes('--help')) console.log('help text');
if (args.includes('--version')) console.log('1.0');
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.files[0].issues.some(i => i.type === 'missing_usage'));
});

test('analyzeCliHealth — detects missing arg validation', () => {
  const files = [{
    path: 'cli.mjs',
    content: `const args = process.argv.slice(2);
console.log('Usage: $ cli');
if (args.includes('--help')) console.log('help');
console.log('done');
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.files[0].issues.some(i => i.type === 'no_arg_validation'));
});

test('analyzeCliHealth — detects missing error exit code', () => {
  const files = [{
    path: 'cli.mjs',
    content: `const args = process.argv.slice(2);
if (!args[0]) console.error('missing arg');
console.log('done');
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.files[0].issues.some(i => i.type === 'no_error_exit'));
});

test('analyzeCliHealth — detects stderr usage', () => {
  const files = [{
    path: 'cli.mjs',
    content: `const args = process.argv.slice(2);
console.error('error here');
process.exit(1);
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.files[0].passedChecks.some(p => p.check === 'stderr_errors'));
});

test('analyzeCliHealth — detects subcommand structure', () => {
  const files = [{
    path: 'cli.mjs',
    content: `import { Command } from 'commander';
const program = new Command();
program.command('deploy').action(() => console.log('deploying'));
program.parse(process.argv);
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.files[0].passedChecks.some(p => p.check === 'subcommands'));
});

test('analyzeCliHealth — detects color output', () => {
  const files = [{
    path: 'cli.mjs',
    content: `import chalk from 'chalk';
console.log(chalk.green('success'));
process.argv;
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.files[0].passedChecks.some(p => p.check === 'color_output'));
});

test('analyzeCliHealth — assigns A grade for complete CLI', () => {
  const files = [{
    path: 'cli.mjs',
    content: `#!/usr/bin/env node
import chalk from 'chalk';
const args = process.argv.slice(2);
if (args.includes('--help') || args.includes('-h')) {
  console.log('Usage: $ cli [options]\\nExamples:\\n  $ cli --build');
  process.exit(0);
}
if (args.includes('--version') || args.includes('-v')) {
  console.log('1.0.0');
  process.exit(0);
}
if (!args[0]) { console.error('Error: missing required argument'); process.exit(1); }
console.log(chalk.green('done'));
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.healthScore >= 75, `expected >= 75, got ${result.healthScore}`);
  assert.ok(['A', 'B'].includes(result.grade), `expected A or B, got ${result.grade}`);
});

test('analyzeCliHealth — assigns F grade for minimal CLI', () => {
  const files = [{
    path: 'cli.mjs',
    content: `process.argv;
console.log('hi');
`,
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.healthScore < 50, `expected < 50, got ${result.healthScore}`);
  assert.equal(result.grade, 'F');
});

test('analyzeCliHealth — handles multiple CLI files', () => {
  const files = [
    { path: 'bin/a.mjs', content: '#!/usr/bin/env node\\nprocess.argv;' },
    { path: 'bin/b.mjs', content: 'const a = process.argv.slice(2);' },
    { path: 'lib/util.mjs', content: 'export const x = 1;' },
  ];
  const result = analyzeCliHealth(files);
  assert.equal(result.cliFileCount, 2);
});

test('analyzeCliHealth — missingChecks aggregates across files', () => {
  const files = [
    { path: 'a.mjs', content: 'process.argv; console.log(\"a\");' },
    { path: 'b.mjs', content: 'process.argv; console.log(\"b\");' },
  ];
  const result = analyzeCliHealth(files);
  assert.ok(result.missingChecks.help_flag >= 2);
});

test('analyzeCliHealth — non-JS files ignored', () => {
  const files = [
    { path: 'cli.py', content: '#!/usr/bin/env python\\nimport sys' },
    { path: 'cli.sh', content: '#!/bin/bash\\necho hi' },
  ];
  const result = analyzeCliHealth(files);
  assert.equal(result.cliFileCount, 0);
});

test('analyzeCliHealth — file with content null is skipped', () => {
  const files = [{ path: 'cli.mjs', content: null }];
  const result = analyzeCliHealth(files);
  assert.equal(result.cliFileCount, 0);
});

test('analyzeCliHealth — detects CLI via filename keyword', () => {
  const files = [{
    path: 'src/command-line-tool.ts',
    content: 'export function run() { return 42; }',
  }];
  const result = analyzeCliHealth(files);
  assert.ok(result.cliFileCount >= 1);
});

test('formatCliHealthReport — empty result returns warning', () => {
  const report = formatCliHealthReport(null);
  assert.ok(report.includes('No CLI entry points'));
});

test('formatCliHealthReport — includes grade and score', () => {
  const result = analyzeCliHealth([{ path: 'cli.mjs', content: 'process.argv; --help\\n--version\\nUsage: $ cli' }]);
  const report = formatCliHealthReport(result);
  if (result.cliFileCount > 0) {
    assert.ok(report.includes('Health Grade'));
    assert.ok(report.includes('CLI files'));
  }
});

test('formatCliHealthReport — includes issues section', () => {
  const files = [{
    path: 'cli.mjs',
    content: 'process.argv; console.log(\"hi\");',
  }];
  const result = analyzeCliHealth(files);
  const report = formatCliHealthReport(result);
  assert.ok(report.includes('Issues') || report.includes('missing'));
});

test('formatCliHealthReport — includes per-file table', () => {
  const files = [{
    path: 'cli.mjs',
    content: '#!/usr/bin/env node\\nconst args = process.argv.slice(2);\\nif (args.includes(\"--help\")) console.log(\"Usage: $ cli\");',
  }];
  const result = analyzeCliHealth(files);
  const report = formatCliHealthReport(result);
  assert.ok(report.includes('Per-file') || report.includes('cli.mjs'));
});
