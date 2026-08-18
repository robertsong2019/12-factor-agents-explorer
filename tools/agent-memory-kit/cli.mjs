#!/usr/bin/env node
// agent-memory-kit (amk) — CLI for AI agent memory management
// Usage: amk <command> [options]
//
// Commands:
//   search <query>           Full-text search across memory files
//   summary                  Show recent memory summary (last 7 days)
//   stats                    Show memory statistics (file count, size, etc.)
//   extract-tags             Extract and count frequent terms/topics
//   timeline                 Show chronological activity timeline
//   merge <src> <dst>        Merge one memory file into another
//   prune <days>             List files older than N days (dry-run)
//   prune <days> --apply     Actually remove old files
//   context [path]           Generate a context snapshot for prompts

import { readFileSync, writeFileSync, readdirSync, statSync, mkdirSync, rmSync, existsSync } from 'fs';
import { join, extname, basename, relative } from 'path';

const HOME = process.env.HOME || '/root';
const WORKSPACE = process.env.OPENCLAW_WORKSPACE || join(HOME, '.openclaw/workspace');
const MEMORY_DIR = join(WORKSPACE, 'memory');
const MEMORY_FILE = join(WORKSPACE, 'MEMORY.md');

const args = process.argv.slice(2);
const command = args[0];

// --- Helpers ---
function getMemoryFiles() {
  if (!existsSync(MEMORY_DIR)) return [];
  return readdirSync(MEMORY_DIR)
    .filter(f => f.endsWith('.md'))
    .map(f => ({ name: f, path: join(MEMORY_DIR, f) }))
    .sort((a, b) => b.name.localeCompare(a.name));
}

function readFileSafe(p) {
  try { return readFileSync(p, 'utf-8'); } catch { return ''; }
}

function formatDate(filename) {
  // e.g. 2026-04-03.md → April 3, 2026
  const m = filename.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return filename;
  const d = new Date(+m[1], +m[2] - 1, +m[3]);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function localDateStr(d) {
  // Memory files are named with LOCAL dates; toISOString() (UTC) misses
  // today's file whenever local date != UTC date (e.g. 00:00-08:00 CST).
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// --- Commands ---
function cmdSearch(query) {
  if (!query) { console.error('Usage: amk search <query>'); process.exit(1); }
  const lower = query.toLowerCase();
  const results = [];
  
  // Search MEMORY.md
  const mem = readFileSafe(MEMORY_FILE);
  if (mem.toLowerCase().includes(lower)) {
    const lines = mem.split('\n').filter(l => l.toLowerCase().includes(lower));
    results.push({ file: 'MEMORY.md', matches: lines });
  }
  
  // Search daily files
  for (const f of getMemoryFiles()) {
    const content = readFileSafe(f.path);
    const lines = content.split('\n').filter(l => l.toLowerCase().includes(lower));
    if (lines.length) results.push({ file: f.name, matches: lines });
  }
  
  if (!results.length) { console.log('No matches found.'); return; }
  for (const r of results) {
    console.log(`\n📄 ${r.file} (${r.matches.length} matches):`);
    for (const line of r.matches.slice(0, 5)) {
      console.log(`   ${line.trim()}`);
    }
    if (r.matches.length > 5) console.log(`   ... and ${r.matches.length - 5} more`);
  }
  console.log(`\nTotal: ${results.length} files, ${results.reduce((s, r) => s + r.matches.length, 0)} matches`);
}

function cmdSummary() {
  const now = new Date();
  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(now - i * 86400000);
    const name = localDateStr(d) + '.md';
    const p = join(MEMORY_DIR, name);
    if (existsSync(p)) {
      const content = readFileSafe(p);
      const lines = content.split('\n').filter(l => l.trim());
      days.push({ date: name, lines: lines.length, preview: lines.slice(0, 3).join('\n') });
    }
  }
  
  console.log('📋 Memory Summary (Last 7 Days)\n');
  if (!days.length) console.log('No memory files found for the last 7 days.');
  for (const d of days) {
    console.log(`  ${formatDate(d.date)} (${d.lines} lines)`);
    console.log(`    ${d.preview.split('\n')[0]?.slice(0, 80) || '(empty)'}`);
  }
  
  // MEMORY.md stats
  if (existsSync(MEMORY_FILE)) {
    const mem = readFileSafe(MEMORY_FILE);
    const memLines = mem.split('\n').filter(l => l.trim()).length;
    console.log(`\n  MEMORY.md: ${memLines} lines, ${mem.length} bytes`);
  }
}

function cmdStats() {
  const files = getMemoryFiles();
  let totalSize = 0, totalLines = 0;
  for (const f of files) {
    const stat = statSync(f.path);
    const content = readFileSafe(f.path);
    totalSize += stat.size;
    totalLines += content.split('\n').filter(l => l.trim()).length;
  }
  
  const memSize = existsSync(MEMORY_FILE) ? statSync(MEMORY_FILE).size : 0;
  const memLines = existsSync(MEMORY_FILE) ? readFileSafe(MEMORY_FILE).split('\n').filter(l => l.trim()).length : 0;
  
  console.log('📊 Memory Statistics\n');
  console.log(`  Daily files:    ${files.length}`);
  console.log(`  Daily size:     ${(totalSize / 1024).toFixed(1)} KB`);
  console.log(`  Daily lines:    ${totalLines}`);
  if (files.length) {
    console.log(`  Earliest:       ${files[files.length - 1].name}`);
    console.log(`  Latest:         ${files[0].name}`);
  }
  console.log(`\n  MEMORY.md:      ${memLines} lines (${(memSize / 1024).toFixed(1)} KB)`);
  console.log(`  Total:          ${((totalSize + memSize) / 1024).toFixed(1)} KB`);
}

function cmdExtractTags() {
  const files = getMemoryFiles();
  const wordFreq = {};
  const stopWords = new Set(['the','a','an','is','are','was','were','be','been','being','have','has','had','do','does','did','will','would','could','should','may','might','shall','can','to','of','in','for','on','with','at','by','from','as','into','through','during','before','after','above','below','between','out','off','over','under','again','further','then','once','here','there','when','where','why','how','all','both','each','few','more','most','other','some','such','no','nor','not','only','own','same','so','than','too','very','just','because','but','and','or','if','while','this','that','these','those','it','its','i','me','my','we','our','you','your','he','him','his','she','her','they','them','their','what','which','who','whom']);
  
  for (const f of files) {
    const content = readFileSafe(f.path);
    const words = content.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, ' ').split(/\s+/).filter(w => w.length > 2 && !stopWords.has(w));
    for (const w of words) {
      wordFreq[w] = (wordFreq[w] || 0) + 1;
    }
  }
  
  // Also scan MEMORY.md
  if (existsSync(MEMORY_FILE)) {
    const content = readFileSafe(MEMORY_FILE);
    const words = content.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, ' ').split(/\s+/).filter(w => w.length > 2 && !stopWords.has(w));
    for (const w of words) wordFreq[w] = (wordFreq[w] || 0) + 1;
  }
  
  const sorted = Object.entries(wordFreq).sort((a, b) => b[1] - a[1]).slice(0, 30);
  console.log('🏷️  Top Terms\n');
  for (const [word, count] of sorted) {
    console.log(`  ${word.padEnd(25)} ${count}`);
  }
}

function cmdTimeline() {
  const files = getMemoryFiles();
  console.log('📅 Activity Timeline\n');
  for (const f of files) {
    const content = readFileSafe(f.path);
    const lines = content.split('\n').filter(l => l.trim());
    const headings = lines.filter(l => l.startsWith('#')).map(l => l.replace(/^#+\s*/, '').slice(0, 60));
    console.log(`  ${formatDate(f.name)} — ${lines.length} lines`);
    for (const h of headings.slice(0, 3)) {
      console.log(`    → ${h}`);
    }
  }
}

function cmdMerge(src, dst) {
  if (!src || !dst) { console.error('Usage: amk merge <source.md> <dest.md>'); process.exit(1); }
  const srcPath = src.includes('/') ? src : join(MEMORY_DIR, src);
  const dstPath = dst.includes('/') ? dst : join(MEMORY_DIR, dst);
  
  const srcContent = readFileSafe(srcPath);
  if (!srcContent) { console.error(`Source not found: ${srcPath}`); process.exit(1); }
  
  const dstContent = readFileSafe(dstPath);
  const merged = dstContent ? dstContent + '\n\n---\n\n' + srcContent : srcContent;
  
  writeFileSync(dstPath, merged, 'utf-8');
  console.log(`✅ Merged ${src} into ${dst}`);
}

function cmdPrune(days, apply = false) {
  if (!days) { console.error('Usage: amk prune <days> [--apply]'); process.exit(1); }
  const cutoff = Date.now() - days * 86400000;
  const files = getMemoryFiles();
  const old = files.filter(f => {
    const m = f.name.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return false;
    return new Date(+m[1], +m[2] - 1, +m[3]).getTime() < cutoff;
  });
  
  if (!old.length) { console.log('No files older than ' + days + ' days.'); return; }
  
  console.log(`🗑️  Files older than ${days} days (${old.length} files):\n`);
  for (const f of old) console.log(`  ${f.name}`);
  
  if (apply) {
    for (const f of old) rmSync(f.path);
    console.log(`\n✅ Removed ${old.length} files.`);
  } else {
    console.log('\n(Dry run — use --apply to actually remove)');
  }
}

function cmdContext(targetPath) {
  const base = targetPath || WORKSPACE;
  const sections = [];
  
  // Gather context
  const identity = readFileSafe(join(base, 'IDENTITY.md'));
  const user = readFileSafe(join(base, 'USER.md'));
  const soul = readFileSafe(join(base, 'SOUL.md'));
  const memory = readFileSafe(MEMORY_FILE);
  const recentFiles = getMemoryFiles().slice(0, 3);
  
  sections.push({ label: 'Identity', content: identity });
  sections.push({ label: 'User', content: user });
  sections.push({ label: 'Soul', content: soul });
  
  for (const f of recentFiles) {
    sections.push({ label: `Memory/${f.name}`, content: readFileSafe(f.path).slice(0, 500) });
  }
  
  if (memory) {
    sections.push({ label: 'Long-term Memory', content: memory.slice(0, 1000) });
  }
  
  const output = sections
    .filter(s => s.content)
    .map(s => `## ${s.label}\n${s.content}`)
    .join('\n\n---\n\n');
  
  console.log(output);
  console.log(`\n📏 Total: ${output.length} chars`);
}

// --- Main ---
switch (command) {
  case 'search': cmdSearch(args[1]); break;
  case 'summary': cmdSummary(); break;
  case 'stats': cmdStats(); break;
  case 'tags':
  case 'extract-tags': cmdExtractTags(); break;
  case 'timeline': cmdTimeline(); break;
  case 'merge': cmdMerge(args[1], args[2]); break;
  case 'prune': cmdPrune(parseInt(args[1]), args.includes('--apply')); break;
  case 'context': cmdContext(args[1]); break;
  default:
    console.log(`agent-memory-kit (amk) v1.0.0
Manage AI agent memory files, session logs, and workspace context.

Usage: amk <command> [options]

Commands:
  search <query>           Full-text search across memory files
  summary                  Recent memory summary (last 7 days)
  stats                    Memory statistics (file count, size, etc.)
  tags                     Extract and count frequent terms/topics
  timeline                 Chronological activity timeline
  merge <src> <dst>        Merge one memory file into another
  prune <days> [--apply]   Remove old files (dry-run by default)
  context [path]           Generate context snapshot for prompts
`);
}
