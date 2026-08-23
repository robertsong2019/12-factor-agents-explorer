/**
 * Core archive logic — storage, search, export.
 * Archive store: ~/.openclaw/session-archives/<id>.json
 */

const fs = require("fs");
const path = require("path");
const os = require("os");

const ARCHIVE_DIR = path.join(
  process.env.SESSION_ARCHIVE_DIR ||
    path.join(os.homedir(), ".openclaw", "session-archives")
);

function ensureDir() {
  if (!fs.existsSync(ARCHIVE_DIR)) {
    fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
  }
}

/**
 * Build a searchable text index from message history.
 */
function buildIndex(history) {
  const tokens = {};
  const messages = Array.isArray(history) ? history : [];

  for (const msg of messages) {
    const text = (msg.content || msg.text || "").toLowerCase();
    const words = text
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .split(/\s+/)
      .filter((w) => w.length > 2);
    for (const w of words) {
      tokens[w] = (tokens[w] || 0) + 1;
    }
  }
  return tokens;
}

/**
 * Archive a session to disk.
 */
function archiveSession({ id, label, history, meta }) {
  ensureDir();
  const messages = Array.isArray(history) ? history : [];
  const now = new Date().toISOString();

  const record = {
    id: id || `session-${Date.now()}`,
    label: label || "",
    archivedAt: now,
    messageCount: messages.length,
    meta: meta || {},
    history: messages,
    index: buildIndex(messages),
  };

  const filePath = path.join(ARCHIVE_DIR, `${record.id}.json`);
  fs.writeFileSync(filePath, JSON.stringify(record, null, 2), "utf-8");

  return { id: record.id, messageCount: record.messageCount, path: filePath };
}

/**
 * List all archives, newest first.
 */
function listArchives({ limit = 50, from, to } = {}) {
  ensureDir();
  const fromMs = from ? new Date(from).getTime() : -Infinity;
  const toMs = to ? new Date(to).getTime() : Infinity;
  const files = fs
    .readdirSync(ARCHIVE_DIR)
    .filter((f) => f.endsWith(".json"))
    .map((f) => {
      try {
        const data = JSON.parse(
          fs.readFileSync(path.join(ARCHIVE_DIR, f), "utf-8")
        );
        return {
          id: data.id,
          label: data.label,
          archivedAt: data.archivedAt,
          messageCount: data.messageCount,
          tags: data.tags || [],
        };
      } catch {
        return null;
      }
    })
    .filter(Boolean)
    .filter((a) => {
      const ts = new Date(a.archivedAt).getTime();
      return ts >= fromMs && ts <= toMs;
    })
    .sort((a, b) => new Date(b.archivedAt) - new Date(a.archivedAt))
    .slice(0, limit);

  return files;
}

/**
 * Full-text search across archives.
 */
function searchArchives(query, { limit = 10 } = {}) {
  ensureDir();
  const q = query.toLowerCase();
  const qWords = q.split(/\s+/).filter((w) => w.length > 2);
  const results = [];

  const files = fs
    .readdirSync(ARCHIVE_DIR)
    .filter((f) => f.endsWith(".json"));

  for (const f of files) {
    try {
      const data = JSON.parse(
        fs.readFileSync(path.join(ARCHIVE_DIR, f), "utf-8")
      );
      let score = 0;
      const matches = [];

      // Token-based scoring
      for (const w of qWords) {
        if (data.index && data.index[w]) {
          score += data.index[w];
        }
      }

      // Exact substring matching on messages
      for (const msg of data.history || []) {
        const text = msg.content || msg.text || "";
        if (text.toLowerCase().includes(q)) {
          score += 10;
          matches.push({
            role: msg.role || "unknown",
            text: text.slice(0, 200),
          });
        }
      }

      if (score > 0) {
        results.push({
          archiveId: data.id,
          label: data.label,
          score,
          matches: matches.slice(0, 5),
        });
      }
    } catch {
      // skip corrupt files
    }
  }

  return results
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

/**
 * Export archived session in various formats.
 */
function exportSession(id, format = "markdown") {
  ensureDir();
  const filePath = path.join(ARCHIVE_DIR, `${id}.json`);
  if (!fs.existsSync(filePath)) {
    // Try partial match
    const files = fs.readdirSync(ARCHIVE_DIR).filter(
      (f) => f.endsWith(".json") && f.startsWith(id)
    );
    if (files.length === 0) throw new Error(`Archive not found: ${id}`);
    return exportSession(files[0].replace(".json", ""), format);
  }

  const data = JSON.parse(fs.readFileSync(filePath, "utf-8"));

  switch (format) {
    case "json":
      return JSON.stringify(data, null, 2);

    case "html":
      return toHtml(data);

    case "markdown":
    default:
      return toMarkdown(data);
  }
}

function toMarkdown(data) {
  let md = `# Session: ${data.label || data.id}\n\n`;
  md += `- **Archived:** ${data.archivedAt}\n`;
  md += `- **Messages:** ${data.messageCount}\n\n---\n\n`;

  for (const msg of data.history || []) {
    const role = msg.role || "unknown";
    const text = msg.content || msg.text || "";
    md += `### ${role.toUpperCase()}\n\n${text}\n\n---\n\n`;
  }
  return md;
}

function toHtml(data) {
  const escLabel = escapeHtml(String(data.label || data.id));
  let html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Session: ${escLabel}</title>
<style>body{font-family:system-ui;max-width:800px;margin:0 auto;padding:20px;color:#333}
.user{background:#e3f2fd;padding:12px;border-radius:8px;margin:8px 0}
.assistant{background:#f1f8e9;padding:12px;border-radius:8px;margin:8px 0}
.system{background:#fff3e0;padding:12px;border-radius:8px;margin:8px 0;font-style:italic}
.tool{background:#fce4ec;padding:12px;border-radius:8px;margin:8px 0;font-family:monospace;font-size:0.9em}
pre{white-space:pre-wrap;word-wrap:break-word}</style></head><body>
<h1>${escLabel}</h1>
<p>Archived: ${data.archivedAt} | Messages: ${data.messageCount}</p><hr>`;

  for (const msg of data.history || []) {
    const role = String(msg.role || "unknown").toLowerCase();
    const roleClass = role.replace(/[^a-z0-9-]/g, "") || "unknown";
    const text = msg.content || msg.text || "";
    html += `<div class="${roleClass}"><strong>${escapeHtml(role)}</strong><pre>${escapeHtml(text)}</pre></div>`;
  }
  html += `</body></html>`;
  return html;
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * Get archive statistics.
 */
function getStats() {
  ensureDir();
  const files = fs
    .readdirSync(ARCHIVE_DIR)
    .filter((f) => f.endsWith(".json"));

  let totalMessages = 0;
  let totalSize = 0;
  let oldest = null;
  let newest = null;

  for (const f of files) {
    const fp = path.join(ARCHIVE_DIR, f);
    totalSize += fs.statSync(fp).size;
    try {
      const data = JSON.parse(fs.readFileSync(fp, "utf-8"));
      totalMessages += data.messageCount || 0;
      if (!oldest || data.archivedAt < oldest) oldest = data.archivedAt;
      if (!newest || data.archivedAt > newest) newest = data.archivedAt;
    } catch {}
  }

  return {
    totalArchives: files.length,
    totalMessages,
    diskUsage:
      totalSize > 1048576
        ? (totalSize / 1048576).toFixed(1) + " MB"
        : (totalSize / 1024).toFixed(1) + " KB",
    oldest: oldest ? new Date(oldest).toLocaleString("zh-CN") : null,
    newest: newest ? new Date(newest).toLocaleString("zh-CN") : null,
  };
}

/**
 * Remove archives older than N days.
 */
function cleanOldArchives(days, dryRun = false) {
  ensureDir();
  const cutoff = Date.now() - days * 86400000;
  const files = fs.readdirSync(ARCHIVE_DIR).filter((f) => f.endsWith(".json"));
  let count = 0;

  for (const f of files) {
    try {
      const data = JSON.parse(
        fs.readFileSync(path.join(ARCHIVE_DIR, f), "utf-8")
      );
      if (new Date(data.archivedAt).getTime() < cutoff) {
        if (!dryRun) {
          fs.unlinkSync(path.join(ARCHIVE_DIR, f));
        }
        count++;
      }
    } catch {}
  }
  return { count };
}

/**
 * Add tags to an archived session.
 */
function addTags(id, tags) {
  const data = _readArchive(id);
  if (!data) throw new Error(`Archive not found: ${id}`);
  data.tags = data.tags || [];
  let added = 0;
  for (const tag of tags) {
    if (!data.tags.includes(tag)) {
      data.tags.push(tag);
      added++;
    }
  }
  _writeArchive(data);
  return { id: data.id, tags: data.tags, added };
}

/**
 * Remove tags from an archived session.
 */
function removeTags(id, tags) {
  const data = _readArchive(id);
  if (!data) throw new Error(`Archive not found: ${id}`);
  data.tags = data.tags || [];
  const before = data.tags.length;
  data.tags = data.tags.filter((t) => !tags.includes(t));
  _writeArchive(data);
  return { id: data.id, tags: data.tags, removed: before - data.tags.length };
}

/**
 * Search archives by tag.
 */
function searchByTag(tag, { limit = 50 } = {}) {
  ensureDir();
  const results = [];
  const files = fs.readdirSync(ARCHIVE_DIR).filter((f) => f.endsWith(".json"));
  for (const f of files) {
    try {
      const data = JSON.parse(fs.readFileSync(path.join(ARCHIVE_DIR, f), "utf-8"));
      if ((data.tags || []).includes(tag)) {
        results.push({
          id: data.id,
          label: data.label,
          archivedAt: data.archivedAt,
          messageCount: data.messageCount,
          tags: data.tags,
        });
      }
    } catch {}
  }
  return results.sort((a, b) => new Date(b.archivedAt) - new Date(a.archivedAt)).slice(0, limit);
}

/** Read a single archive by id. */
function _readArchive(id) {
  ensureDir();
  const filePath = path.join(ARCHIVE_DIR, `${id}.json`);
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

/** Write archive data back to disk. */
function _writeArchive(data) {
  ensureDir();
  const filePath = path.join(ARCHIVE_DIR, `${data.id}.json`);
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf-8");
}

/**
 * Merge multiple archives into one combined session.
 * Messages are concatenated in chronological order (by source archivedAt).
 */
function mergeArchives(ids, { label, id } = {}) {
  if (!Array.isArray(ids) || ids.length < 2) {
    throw new Error("mergeArchives requires at least 2 archive ids");
  }

  const archives = ids.map((aid) => {
    const data = _readArchive(aid);
    if (!data) throw new Error(`Archive not found: ${aid}`);
    return data;
  });

  // Sort sources by archivedAt to keep chronological order
  archives.sort((a, b) => new Date(a.archivedAt) - new Date(b.archivedAt));

  const mergedHistory = [];
  const mergedMeta = { sources: [] };
  const allTags = new Set();

  for (const src of archives) {
    for (const msg of src.history || []) {
      mergedHistory.push({ ...msg, _source: src.id });
    }
    mergedMeta.sources.push({ id: src.id, label: src.label, archivedAt: src.archivedAt, messageCount: src.messageCount });
    for (const t of src.tags || []) allTags.add(t);
  }

  const mergedId = id || `merged-${Date.now()}`;
  const result = archiveSession({
    id: mergedId,
    label: label || archives.map((a) => a.label || a.id).join(" + "),
    history: mergedHistory,
    meta: mergedMeta,
  });

  // Apply merged tags
  if (allTags.size > 0) {
    addTags(mergedId, [...allTags]);
  }

  return { ...result, sourceCount: archives.length, totalMessages: mergedHistory.length };
}

/**
 * Compare two archived sessions and return a diff summary.
 */
function diffArchives(idA, idB) {
  const a = _readArchive(idA);
  const b = _readArchive(idB);
  if (!a) throw new Error(`Archive not found: ${idA}`);
  if (!b) throw new Error(`Archive not found: ${idB}`);

  const setA = new Set((a.history || []).map((m) => `${m.role}:${(m.content || m.text || "").trim()}`));
  const setB = new Set((b.history || []).map((m) => `${m.role}:${(m.content || m.text || "").trim()}`));

  const onlyInA = (a.history || []).filter((m) => !setB.has(`${m.role}:${(m.content || m.text || "").trim()}`));
  const onlyInB = (b.history || []).filter((m) => !setA.has(`${m.role}:${(m.content || m.text || "").trim()}`));
  const common = (a.history || []).filter((m) => setB.has(`${m.role}:${(m.content || m.text || "").trim()}`));

  return {
    a: { id: a.id, label: a.label, messageCount: a.messageCount },
    b: { id: b.id, label: b.label, messageCount: b.messageCount },
    onlyInA: onlyInA.map((m) => ({ role: m.role, text: (m.content || m.text || "").slice(0, 200) })),
    onlyInB: onlyInB.map((m) => ({ role: m.role, text: (m.content || m.text || "").slice(0, 200) })),
    commonCount: common.length,
    similarity: a.messageCount + b.messageCount > 0
      ? (2 * common.length / (a.messageCount + b.messageCount)).toFixed(2)
      : "0.00",
  };
}

module.exports = {
  archiveSession,
  listArchives,
  searchArchives,
  exportSession,
  getStats,
  cleanOldArchives,
  addTags,
  removeTags,
  searchByTag,
  mergeArchives,
  diffArchives,
};
