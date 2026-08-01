/**
 * OpenClaw API integration — fetch live sessions and history.
 * Uses the OpenClaw gateway's local API (sessions_list, sessions_history tools).
 *
 * When running inside an OpenClaw agent, this module provides helpers
 * that format data for the archive module.
 * When used standalone, it reads from the gateway's data directory.
 */

const fs = require("fs");
const path = require("path");
const os = require("os");

function getOpenclawHome() {
  return process.env.OPENCLAW_HOME || path.join(os.homedir(), ".openclaw");
}

/**
 * Attempt to list live sessions by reading OpenClaw's data.
 * In standalone mode, this is a best-effort scan.
 */
async function listLiveSessions() {
  // When running inside OpenClaw, the agent can use sessions_list tool.
  // Standalone: we provide a placeholder that the CLI user can fill.
  // For now, return an empty array with instructions.
  return [];
}

/**
 * Fetch session history by session key.
 * Standalone: reads from OpenClaw's session store if accessible.
 */
async function fetchSessionHistory(sessionKey) {
  // When running inside OpenClaw agent, use sessions_history tool.
  // Standalone fallback: try to find session files
  const sessionsDir = path.join(getOpenclawHome(), "sessions");
  if (fs.existsSync(sessionsDir)) {
    const files = fs.readdirSync(sessionsDir).filter((f) => f.includes(sessionKey));
    if (files.length > 0) {
      const content = fs.readFileSync(path.join(sessionsDir, files[0]), "utf-8");
      try {
        return JSON.parse(content);
      } catch {
        // Try line-delimited JSON
        return content
          .split("\n")
          .filter((l) => l.trim())
          .map((l) => {
            try { return JSON.parse(l); } catch { return { text: l }; }
          });
      }
    }
  }
  return [];
}

module.exports = { listLiveSessions, fetchSessionHistory };
