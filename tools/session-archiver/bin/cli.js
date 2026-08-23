#!/usr/bin/env node
/**
 * session-archiver — Archive, search, and export OpenClaw session histories.
 *
 * Usage:
 *   session-archiver list              List archived sessions
 *   session-archiver archive <id>      Archive a session to local store
 *   session-archiver search <query>    Full-text search across archives
 *   session-archiver export <id>       Export session as markdown/html/json
 *   session-archiver stats             Show archive statistics
 *   session-archiver clean [--days N]  Remove archives older than N days (default 90)
 */

const { Command, InvalidArgumentError } = require("commander");
const {
  archiveSession,
  listArchives,
  searchArchives,
  exportSession,
  getStats,
  cleanOldArchives,
} = require("../lib/archive");
const {
  listLiveSessions,
  fetchSessionHistory,
} = require("../lib/openclaw-api");
const path = require("path");

// Fallback chalk for environments without it
let c = {
  green: (s) => s,
  yellow: (s) => s,
  red: (s) => s,
  cyan: (s) => s,
  bold: (s) => s,
  dim: (s) => s,
  gray: (s) => s,
};
try {
  c = require("chalk");
} catch (_) {}

// Commander coercion: reject non-numeric values instead of silently producing NaN
function parseNum(v) {
  const n = parseInt(v, 10);
  if (Number.isNaN(n) || n < 0) {
    throw new InvalidArgumentError("expected a non-negative integer");
  }
  return n;
}

const program = new Command();

program
  .name("session-archiver")
  .description("Archive, search, and export OpenClaw agent session histories")
  .version("1.0.0");

// --- list ---
program
  .command("list")
  .description("List archived sessions")
  .option("-l, --limit <n>", "Max results", parseNum, 20)
  .option("--json", "Output as JSON")
  .action(async (opts) => {
    const archives = listArchives({ limit: opts.limit });
    if (opts.json) {
      console.log(JSON.stringify(archives, null, 2));
      return;
    }
    if (archives.length === 0) {
      console.log(c.yellow("No archived sessions found."));
      return;
    }
    console.log(c.bold(`\n📋 Archived Sessions (${archives.length})\n`));
    for (const a of archives) {
      const date = new Date(a.archivedAt).toLocaleString("zh-CN");
      console.log(
        `  ${c.cyan(a.id.slice(0, 12))}…  ${c.dim(date)}  ${c.green(a.messageCount + " msgs")}  ${a.label || ""}`
      );
    }
    console.log();
  });

// --- archive ---
program
  .command("archive")
  .description("Archive sessions (live or by ID)")
  .option("--all", "Archive all live sessions")
  .option("--id <id>", "Archive specific session ID")
  .option("--label <label>", "Label for the archive")
  .action(async (opts) => {
    try {
      if (opts.all) {
        const sessions = await listLiveSessions();
        if (!sessions.length) {
          console.log(c.yellow("No live sessions found."));
          return;
        }
        console.log(c.bold(`\n📦 Archiving ${sessions.length} sessions…\n`));
        for (const s of sessions) {
          const history = await fetchSessionHistory(s.key || s.id);
          const result = archiveSession({
            id: s.key || s.id,
            label: s.label || opts.label,
            history,
            meta: s,
          });
          console.log(`  ${c.green("✓")} ${result.id.slice(0, 12)}… (${result.messageCount} msgs)`);
        }
        console.log(c.green("\nDone!"));
      } else if (opts.id) {
        const history = await fetchSessionHistory(opts.id);
        const result = archiveSession({
          id: opts.id,
          label: opts.label,
          history,
        });
        console.log(c.green(`✓ Archived ${result.id.slice(0, 12)}… (${result.messageCount} messages)`));
      } else {
        console.log(c.red("Specify --all or --id <session-id>"));
        process.exitCode = 1;
      }
    } catch (err) {
      console.error(c.red(`Error: ${err.message}`));
      process.exitCode = 1;
    }
  });

// --- search ---
program
  .command("search <query>")
  .description("Full-text search across archived sessions")
  .option("-l, --limit <n>", "Max results", parseNum, 10)
  .option("--json", "Output as JSON")
  .action((query, opts) => {
    const results = searchArchives(query, { limit: opts.limit });
    if (opts.json) {
      console.log(JSON.stringify(results, null, 2));
      return;
    }
    if (results.length === 0) {
      console.log(c.yellow(`No results for "${query}"`));
      return;
    }
    console.log(c.bold(`\n🔍 Results for "${query}" (${results.length})\n`));
    for (const r of results) {
      console.log(`  ${c.cyan(r.archiveId.slice(0, 12))}…  ${c.dim("score:" + r.score)}`);
      for (const m of r.matches.slice(0, 3)) {
        const preview = m.text.slice(0, 120).replace(/\n/g, " ");
        console.log(`    ${c.gray("›")} ${preview}…`);
      }
    }
    console.log();
  });

// --- export ---
program
  .command("export <id>")
  .description("Export an archived session")
  .option("-f, --format <fmt>", "Output format: markdown, html, json", "markdown")
  .option("-o, --output <file>", "Output file (default: stdout)")
  .action((id, opts) => {
    let content;
    try {
      content = exportSession(id, opts.format);
    } catch (err) {
      console.error(c.red(`Error: ${err.message}`));
      process.exitCode = 1;
      return;
    }
    if (opts.output) {
      require("fs").writeFileSync(opts.output, content, "utf-8");
      console.log(c.green(`✓ Exported to ${opts.output}`));
    } else {
      console.log(content);
    }
  });

// --- stats ---
program.command("stats").description("Show archive statistics").action(() => {
  const stats = getStats();
  console.log(c.bold("\n📊 Archive Statistics\n"));
  console.log(`  Total archives:   ${c.green(stats.totalArchives)}`);
  console.log(`  Total messages:   ${c.green(stats.totalMessages)}`);
  console.log(`  Disk usage:       ${c.cyan(stats.diskUsage)}`);
  console.log(`  Oldest archive:   ${stats.oldest || "N/A"}`);
  console.log(`  Newest archive:   ${stats.newest || "N/A"}`);
  console.log();
});

// --- clean ---
program
  .command("clean")
  .description("Remove archives older than N days")
  .option("--days <n>", "Days threshold", parseNum, 90)
  .option("--dry-run", "Show what would be deleted")
  .action((opts) => {
    const result = cleanOldArchives(opts.days, opts.dryRun);
    if (opts.dryRun) {
      console.log(c.yellow(`Would remove ${result.count} archives (older than ${opts.days} days)`));
    } else {
      console.log(c.green(`✓ Removed ${result.count} old archives`));
    }
  });

program.parse();
