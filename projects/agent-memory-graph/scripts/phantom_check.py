#!/usr/bin/env python3
"""
Phantom Commit Detector — pre-commit guard against class shadowing & phantom APIs.

Problem (07-07 incident): 6 APIs were committed but didn't actually exist in code.
Root cause: class shadowing — duplicate class definitions where the second silently
overwrites the first, and TDD blind spots let it pass.

This script runs as a pre-commit hook. It:
1. Detects duplicate class/function definitions within the same file (shadowing)
2. Parses staged commit message for API names, verifies they exist in code
3. Reports violations clearly

Usage:
    python3 scripts/phantom_check.py          # check all .py files
    python3 scripts/phantom_check.py file.py   # check specific file
    python3 scripts/phantom_check.py --commit-msg .git/COMMIT_EDITMSG  # verify commit msg

Exit codes:
    0 = clean
    1 = phantom/shadowing detected
"""

import ast
import sys
import os
import re
from pathlib import Path
from collections import defaultdict


def find_definitions(filepath: str) -> dict[str, list[int]]:
    """Parse a Python file, return {name: [line_numbers]} for all top-level + nested class/def."""
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)
    except (SyntaxError, FileNotFoundError, UnicodeDecodeError):
        return {}

    defs: dict[str, list[int]] = defaultdict(list)

    def _walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                full_name = f"{prefix}{child.name}" if not prefix else f"{prefix}.{child.name}"
                defs[full_name].append(child.lineno)
                _walk(child, full_name)
            elif not isinstance(child, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)):
                _walk(child, prefix)

    _walk(tree)
    return dict(defs)


def detect_shadowing(filepath: str) -> list[tuple[str, list[int]]]:
    """Find class/function names defined more than once in the same file."""
    defs = find_definitions(filepath)
    return [(name, lines) for name, lines in defs.items() if len(lines) > 1]


def extract_api_names_from_commit_msg(msg: str) -> list[str]:
    """Extract likely API names from a commit message.

    Looks for patterns like:
    - `function_name()` or `ClassName`
    - backtick-quoted identifiers (with or without trailing ())
    - snake_case words (bare or followed by ())
    """
    apis = set()

    # Backtick-quoted identifiers: `some_api` or `some_api()`
    for m in re.finditer(r'`([a-zA-Z_][a-zA-Z0-9_]*)\s*\(?\)?`', msg):
        apis.add(m.group(1))

    # snake_case words: bare or followed by (): like retrieve() or edge_current_flow_betweenness
    for m in re.finditer(r'\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\s*\(?\)?', msg):
        apis.add(m.group(1))

    # CamelCase identifiers (potential class names): mentioned explicitly
    for m in re.finditer(r'\b([A-Z][a-zA-Z0-9]+)\b', msg):
        name = m.group(1)
        # Skip common English words that look like CamelCase
        if name not in {"The", "This", "That", "These", "Those", "Brandes", "Fleischer",
                        "Kirchhoff", "Matrix", "Tree", "Gutman", "Balaban", "Randic",
                        "Wiener", "Laplacian", "Python", "SQLite", "Commit", "Cycle",
                        "Lamport", "Ebbinghaus", "Bron", "Kerbosch", "Leiden",
                        "LoCoMo", "PPR", "RRF", "CRDT", "QDAP", "SkewRoute",
                        "CF", "API", "APIs", "TDD", "AST"}:
            apis.add(name)

    return list(apis)


def verify_apis_exist(api_names: list[str], source_files: list[str]) -> list[tuple[str, str]]:
    """Check that each API name exists as a definition in at least one source file.

    Returns list of (api_name, status) tuples where status is 'missing' or 'found'.
    """
    all_defs: set[str] = set()
    for sf in source_files:
        defs = find_definitions(sf)
        # Add both full names and short names (last component after .)
        for name in defs:
            all_defs.add(name)
            short = name.split(".")[-1]
            all_defs.add(short)

    results = []
    for api in api_names:
        # Check exact match or as substring of a definition
        found = api in all_defs or any(api in d for d in all_defs)
        results.append((api, "found" if found else "missing"))

    return results


def check_files(filepaths: list[str]) -> dict:
    """Run all checks on given files. Returns report dict."""
    report = {
        "shadowing": [],
        "total_defs": 0,
        "files_checked": 0,
    }

    for fp in filepaths:
        if not fp.endswith(".py") or not os.path.exists(fp):
            continue

        report["files_checked"] += 1
        defs = find_definitions(fp)
        report["total_defs"] += len(defs)

        shadows = detect_shadowing(fp)
        for name, lines in shadows:
            report["shadowing"].append({
                "file": fp,
                "name": name,
                "lines": lines,
            })

    return report


def format_report(report: dict) -> str:
    """Human-readable report."""
    lines = []
    lines.append(f"📁 Files checked: {report['files_checked']}")
    lines.append(f"📋 Definitions found: {report['total_defs']}")

    if report["shadowing"]:
        lines.append(f"\n🚨 SHADOWING DETECTED ({len(report['shadowing'])} case(s)):")
        for s in report["shadowing"]:
            lines.append(f"  {s['file']}: '{s['name']}' defined at lines {s['lines']}")
    else:
        lines.append("✅ No shadowing detected")

    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    commit_msg_path = None

    if "--commit-msg" in args:
        idx = args.index("--commit-msg")
        commit_msg_path = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    # Determine files to check
    if args:
        files = args
    else:
        # Auto-discover .py files in project root (not in venv, __pycache__, dist, etc.)
        root = Path(__file__).parent.parent
        exclude = {"__pycache__", "dist", ".egg-info", ".git", "node_modules",
                   "venv", ".venv", "site-packages", "lib", "env", ".env", ".tox"}
        files = []
        for p in root.rglob("*.py"):
            if not any(part in exclude for part in p.parts):
                files.append(str(p))

    report = check_files(files)
    print(format_report(report))

    # Verify commit message APIs if provided
    phantom_apis = []
    if commit_msg_path and os.path.exists(commit_msg_path):
        with open(commit_msg_path) as f:
            msg = f.read()
        api_names = extract_api_names_from_commit_msg(msg)
        if api_names:
            results = verify_apis_exist(api_names, files)
            missing = [(a, s) for a, s in results if s == "missing"]
            if missing:
                print(f"\n🚨 PHANTOM APIs in commit message ({len(missing)}):")
                for api, _ in missing:
                    print(f"  '{api}' — NOT FOUND in any source file")
                phantom_apis = missing
            else:
                print(f"\n✅ All {len(api_names)} commit-message APIs verified in code")

    # Exit non-zero on any issue
    if report["shadowing"] or phantom_apis:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
