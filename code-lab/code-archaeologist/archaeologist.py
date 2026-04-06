#!/usr/bin/env python3
"""
Code Archaeologist — Excavate the story hidden in git history.

Usage: python3 archaeologist.py /path/to/git/repo [--output report.md] [--json]
"""

import subprocess
import os
import sys
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from pathlib import Path


def run_git(repo_path, *args):
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path] + list(args),
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_log(repo_path):
    """Parse git log into structured data."""
    fmt = "%H|%an|%ae|%at|%s"
    raw = run_git(repo_path, "log", f"--pretty=format:{fmt}")
    if not raw:
        return []
    
    entries = []
    for line in raw.split("\n"):
        parts = line.split("|", 4)
        if len(parts) == 5:
            entries.append({
                "hash": parts[0][:8],
                "author": parts[1],
                "email": parts[2],
                "timestamp": int(parts[3]),
                "subject": parts[4],
            })
    return entries


def get_file_churn(repo_path):
    """Get per-file churn (added/removed lines) from git log."""
    raw = run_git(repo_path, "log", "--numstat", "--format=")
    churn = defaultdict(lambda: {"added": 0, "removed": 0})
    for line in raw.split("\n"):
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            f = parts[2]
            # Skip binary files
            churn[f]["added"] += int(parts[0])
            churn[f]["removed"] += int(parts[1])
    return dict(churn)


def get_file_count_over_time(repo_path, num_samples=10):
    """Sample file count at different points in history."""
    raw = run_git(repo_path, "log", "--reverse", "--format=%at")
    if not raw:
        return []
    timestamps = [int(t) for t in raw.split("\n") if t.strip()]
    if not timestamps:
        return []
    
    # Sample evenly
    step = max(1, len(timestamps) // num_samples)
    samples = timestamps[::step][-num_samples:]
    
    result = []
    for ts in samples:
        # Count files at this commit
        date = datetime.fromtimestamp(ts)
        out = run_git(repo_path, "ls-tree", "-r", "--name-only", f"--before={date.isoformat()}", "HEAD")
        # Fallback: use git log to find commit at that time
        commit_hash = run_git(repo_path, "rev-list", "-1", "--before", str(ts), "HEAD")
        if commit_hash:
            out = run_git(repo_path, "ls-tree", "-r", "--name-only", commit_hash)
            count = len([l for l in out.split("\n") if l.strip()])
            result.append({"date": date.strftime("%Y-%m-%d"), "files": count})
    return result


def classify_commit(subject):
    """Classify commit type from subject line."""
    s = subject.lower()
    if any(w in s for w in ["fix", "bug", "patch", "hotfix"]):
        return "fix"
    if any(w in s for w in ["feat", "add", "new", "create", "implement"]):
        return "feature"
    if any(w in s for w in ["refactor", "clean", "restructure", "reorganize", "move"]):
        return "refactor"
    if any(w in s for w in ["test", "spec", "coverage"]):
        return "test"
    if any(w in s for w in ["doc", "readme", "comment", "changelog"]):
        return "docs"
    if any(w in s for w in ["ci", "build", "deploy", "release", "version"]):
        return "infra"
    return "other"


def detect_phases(entries):
    """Detect development phases from commit patterns."""
    if len(entries) < 5:
        return [{"name": "Activity", "start": 0, "end": len(entries)}]
    
    # Reverse to chronological order
    entries = list(reversed(entries))
    total = len(entries)
    
    # Sliding window activity analysis
    window = max(5, total // 10)
    phases = []
    
    # Simple phase detection: group by activity level clusters
    chunk_size = max(5, total // 6)
    phase_names = ["Foundation", "Growth", "Expansion", "Maturation", "Refactoring", "Stabilization"]
    
    for i in range(0, total, chunk_size):
        chunk = entries[i:i+chunk_size]
        if not chunk:
            break
        
        types = Counter(classify_commit(e["subject"]) for e in chunk)
        authors = set(e["author"] for e in chunk)
        dates = [datetime.fromtimestamp(e["timestamp"]) for e in chunk]
        
        # Name the phase based on dominant activity
        dominant = types.most_common(1)[0][0] if types else "other"
        name_map = {
            "feature": "Development",
            "fix": "Bugfixing",
            "refactor": "Refactoring",
            "test": "Hardening",
            "docs": "Documentation",
            "infra": "Infrastructure",
            "other": "Activity",
        }
        
        phase_idx = min(len(phases), len(phase_names) - 1)
        phases.append({
            "name": f"{phase_names[phase_idx]} Period",
            "type": name_map.get(dominant, "Activity"),
            "start_date": min(dates).strftime("%Y-%m-%d"),
            "end_date": max(dates).strftime("%Y-%m-%d"),
            "commits": len(chunk),
            "authors": list(authors),
            "types": dict(types),
            "dominant": dominant,
        })
    
    return phases


def generate_narrative(repo_path):
    """Generate the full archaeological report."""
    name = os.path.basename(os.path.abspath(repo_path))
    entries = get_log(repo_path)
    
    if not entries:
        return f"⚠️  No git history found in {repo_path}"
    
    churn = get_file_churn(repo_path)
    authors = Counter(e["author"] for e in entries)
    types = Counter(classify_commit(e["subject"]) for e in entries)
    
    first = datetime.fromtimestamp(entries[-1]["timestamp"])
    last = datetime.fromtimestamp(entries[0]["timestamp"])
    duration = last - first
    
    phases = detect_phases(entries)
    
    # Top hotspots (most changed files)
    hotspots = sorted(churn.items(), key=lambda x: x[1]["added"] + x[1]["removed"], reverse=True)[:10]
    
    # Build report
    lines = []
    lines.append(f"🏛️  EXCAVATION REPORT: {name}")
    lines.append("═" * 50)
    lines.append("")
    lines.append(f"📍 SITE: {name} ({len(entries)} commits, {len(churn)} files, {len(authors)} contributors)")
    lines.append(f"⏰ STRATA: {first.strftime('%Y-%m-%d')} → {last.strftime('%Y-%m-%d')} ({duration.days} days)")
    lines.append("")
    
    # Phases
    for i, phase in enumerate(phases, 1):
        lines.append(f"LAYER {i} — {phase['name']} ({phase['start_date']} ~ {phase['end_date']})")
        lines.append(f"  Settlers: {', '.join(phase['authors'][:5])}")
        lines.append(f"  Activity: {phase['commits']} commits | Focus: {phase['type']}")
        
        type_str = ", ".join(f"{v} {k}" for k, v in sorted(phase["types"].items(), key=lambda x: -x[1])[:3])
        lines.append(f"  Breakdown: {type_str}")
        
        # Detect warnings
        if phase["dominant"] == "fix" and phase["commits"] > 10:
            lines.append("  ⚠️  Bug-heavy period — possible instability")
        if phase["dominant"] == "refactor":
            lines.append("  🔨 Structural overhaul detected")
        if len(phase["authors"]) == 1 and phase["commits"] > 15:
            lines.append("  👤 Solo development phase")
        
        lines.append("")
    
    # Contributors
    lines.append("👤 KEY FIGURES")
    for author, count in authors.most_common(5):
        pct = count / len(entries) * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"  {author:20s} {bar} {count} commits ({pct:.0f}%)")
    lines.append("")
    
    # Hotspots
    lines.append("🔥 EXCAVATION HOTSPOTS (most churned files)")
    for path, stats in hotspots[:7]:
        total = stats["added"] + stats["removed"]
        # Shorten path
        short = "/".join(Path(path).parts[-3:]) if len(Path(path).parts) > 3 else path
        lines.append(f"  {short:40s} +{stats['added']:-6d} / -{stats['removed']:-6d}  ({total} lines)")
    lines.append("")
    
    # Commit type distribution
    lines.append("📊 ARTIFACT CLASSIFICATION")
    type_emoji = {"feature": "✨", "fix": "🐛", "refactor": "🔨", "test": "🧪", "docs": "📝", "infra": "⚙️", "other": "📦"}
    for t, count in types.most_common():
        pct = count / len(entries) * 100
        bar = "▓" * int(pct / 3) + "░" * (33 - int(pct / 3))
        emoji = type_emoji.get(t, "📦")
        lines.append(f"  {emoji} {t:12s} {bar} {count} ({pct:.0f}%)")
    lines.append("")
    
    # Summary insights
    lines.append("💡 ARCHAEOLOGICAL INSIGHTS")
    
    # Bus factor
    if len(authors) > 1:
        top_pct = authors.most_common(1)[0][1] / len(entries) * 100
        if top_pct > 60:
            lines.append(f"  ⚠️  Low bus factor: {authors.most_common(1)[0][0]} authored {top_pct:.0f}% of commits")
    
    # Weekend warriors
    weekend_commits = sum(1 for e in entries if datetime.fromtimestamp(e["timestamp"]).weekday() >= 5)
    wk_pct = weekend_commits / len(entries) * 100
    if wk_pct > 25:
        lines.append(f"  🌙 Night owls: {wk_pct:.0f}% of commits on weekends")
    
    # Velocity trend
    if len(entries) > 20:
        recent = entries[:len(entries)//4]
        older = entries[len(entries)//4:len(entries)//2]
        if recent and older:
            r_rate = len(recent) / max(1, (datetime.fromtimestamp(recent[0]["timestamp"]) - datetime.fromtimestamp(recent[-1]["timestamp"])).days)
            o_rate = len(older) / max(1, (datetime.fromtimestamp(older[0]["timestamp"]) - datetime.fromtimestamp(older[-1]["timestamp"])).days)
            if o_rate > 0:
                trend = r_rate / o_rate
                if trend > 1.5:
                    lines.append(f"  📈 Accelerating: {trend:.1f}x more commits recently")
                elif trend < 0.5:
                    lines.append(f"  📉 Slowing down: {trend:.1f}x fewer commits recently")
    
    if not any("⚠️" in l or "📈" in l or "📉" in l or "🌙" in l for l in lines[-5:]):
        lines.append("  ✅ Healthy project with balanced activity patterns")
    
    lines.append("")
    lines.append("═" * 50)
    lines.append(f"Excavated at {datetime.now().strftime('%Y-%m-%d %H:%M')} by Code Archaeologist 🔍")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 archaeologist.py /path/to/git/repo [--output report.md] [--json]")
        sys.exit(1)
    
    repo = sys.argv[1]
    output_file = None
    as_json = False
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--json":
            as_json = True
            i += 1
        else:
            i += 1
    
    report = generate_narrative(repo)
    
    if as_json:
        # Return structured data
        entries = get_log(repo)
        churn = get_file_churn(repo_path=repo)
        data = {
            "repo": os.path.basename(os.path.abspath(repo)),
            "total_commits": len(entries),
            "contributors": dict(Counter(e["author"] for e in entries)),
            "phases": detect_phases(entries),
            "churn": {k: v for k, v in sorted(churn.items(), key=lambda x: -(x[1]["added"]+x[1]["removed"]))[:20]},
            "narrative": report,
        }
        print(json.dumps(data, indent=2, default=str))
    else:
        print(report)
    
    if output_file:
        with open(output_file, "w") as f:
            f.write(report)
        print(f"\n📄 Report saved to {output_file}")


if __name__ == "__main__":
    main()
