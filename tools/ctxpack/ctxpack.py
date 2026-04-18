#!/usr/bin/env python3
"""
ctxpack — Generate optimized context files for AI coding agents.

Analyzes a project directory and produces a structured context file
that helps AI agents understand your codebase.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Optional

# ── Constants ──────────────────────────────────────────────────────────

VERSION = "0.1.0"

DEFAULT_IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", ".nuxt", "dist",
    "build", "out", ".cache", ".turbo", "target", "vendor", ".venv",
    "venv", "env", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "coverage", ".coverage", "htmlcov", ".terraform", ".serverless",
    " Pods", ".gradle", ".idea", ".vscode", "*.egg-info",
}

DEFAULT_IGNORE_FILES = {
    "*.lock", "*.log", "*.pyc", "*.pyo", ".DS_Store", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "Gemfile.lock", "poetry.lock",
}

IGNORE_PATTERNS = set()

KEY_FILE_PATTERNS = {
    "entry": [
        "index.{ts,js,py,go,rs}", "main.{ts,js,py,go,rs}", "app.{ts,js,py}",
        "src/index.{ts,tsx,js,jsx}", "src/main.{ts,tsx,js,py}",
        "cmd/*/main.go", "src/lib.rs", "mod.ts",
    ],
    "config": [
        "package.json", "tsconfig.json", "pyproject.toml", "Cargo.toml",
        "go.mod", "Makefile", "Dockerfile", "docker-compose.{yml,yaml}",
        ".env.example", "vite.config.*", "next.config.*", "nuxt.config.*",
        "webpack.config.*", "rollup.config.*", "jest.config.*",
        "vitest.config.*", ".eslintrc.*", ".prettierrc.*",
        "tailwind.config.*", "postcss.config.*",
    ],
    "schema": [
        "*.schema.{ts,js,json}", "*.prisma", "schema.prisma",
        "migrations/*", "drizzle.config.*",
    ],
    "agent_context": [
        "AGENTS.md", "CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md",
        "CONTEXT.md", "PROMPT.md", "SPEC.md",
    ],
    "docs": [
        "README.md", "CONTRIBUTING.md", "CHANGELOG.md", "API.md",
        "docs/**/*.md",
    ],
    "test": [
        "**/__tests__/**", "**/*.test.{ts,js,py}", "**/*.spec.{ts,js,py}",
        "tests/**", "test/**",
    ],
}

FRAMEWORK_DETECTORS = {
    "next": ["next.config.js", "next.config.mjs", "next.config.ts"],
    "nuxt": ["nuxt.config.js", "nuxt.config.ts"],
    "react": None,  # detected from package.json deps
    "vue": None,
    "fastapi": None,
    "django": None,
    "express": None,
    "flask": None,
    "hono": None,
}

MAX_FILE_READ = 8000  # chars per file
MAX_CONTEXT_SIZE = 50000  # chars total before warning


# ── Helpers ────────────────────────────────────────────────────────────

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English/code."""
    return len(text) // 4


def truncate(content: str, max_len: int = MAX_FILE_READ) -> str:
    if len(content) <= max_len:
        return content
    return content[:max_len] + "\n... (truncated)"


def load_gitignore(root: Path) -> set[str]:
    """Load patterns from .gitignore."""
    patterns = set()
    gi = root / ".gitignore"
    if gi.exists():
        for line in gi.read_text(errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.add(line)
    return patterns


def should_ignore(path: str, gitignore_patterns: set[str]) -> bool:
    name = os.path.basename(path)
    for d in DEFAULT_IGNORE_DIRS:
        if fnmatch.fnmatch(name, d):
            return True
    for p in DEFAULT_IGNORE_FILES:
        if fnmatch.fnmatch(name, p):
            return True
    for p in gitignore_patterns:
        if fnmatch.fnmatch(name, p) or fnmatch.fnmatch(path, p):
            return True
    return False


def scan_tree(root: Path, gitignore: set[str], max_depth: int = 4):
    """Walk directory tree and collect files."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = rel.count(os.sep) if rel != "." else 0
        if depth >= max_depth:
            dirnames.clear()
            continue
        # Filter dirs in-place
        dirnames[:] = [
            d for d in dirnames
            if not should_ignore(os.path.join(rel, d), gitignore)
        ]
        for f in filenames:
            fp = os.path.join(rel, f) if rel != "." else f
            if not should_ignore(fp, gitignore):
                files.append(fp)
    return sorted(files)


def detect_languages(files: list[str]) -> list[str]:
    """Detect programming languages from file extensions."""
    ext_map = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go",
        ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
        ".rb": "Ruby", ".php": "PHP", ".cs": "C#",
        ".swift": "Swift", ".c": "C", ".cpp": "C++",
    }
    langs = set()
    for f in files:
        ext = os.path.splitext(f)[1]
        if ext in ext_map:
            langs.add(ext_map[ext])
    return sorted(langs)


def detect_frameworks(root: Path, files: list[str]) -> list[str]:
    """Detect frameworks used in the project."""
    frameworks = []

    # File-based detection
    for fw, detectors in FRAMEWORK_DETECTORS.items():
        if detectors is None:
            continue
        for det in detectors:
            if any(fnmatch.fnmatch(f, det) for f in files):
                frameworks.append(fw)

    # Package.json based detection
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(errors="ignore"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "react" in deps and "next" not in frameworks:
                frameworks.append("react")
            if "vue" in deps and "nuxt" not in frameworks:
                frameworks.append("vue")
            if "express" in deps:
                frameworks.append("express")
            if "hono" in deps:
                frameworks.append("hono")
            if "fastify" in deps:
                frameworks.append("fastify")
        except Exception:
            pass

    # Python
    req = root / "requirements.txt"
    pyproject = root / "pyproject.toml"
    for pf in [req, pyproject]:
        if pf.exists():
            try:
                content = pf.read_text(errors="ignore").lower()
                if "fastapi" in content:
                    frameworks.append("fastapi")
                if "django" in content:
                    frameworks.append("django")
                if "flask" in content:
                    frameworks.append("flask")
            except Exception:
                pass

    return sorted(set(frameworks))


def find_key_files(files: list[str], root: Path) -> dict[str, list[str]]:
    """Categorize files by role."""
    result = {k: [] for k in KEY_FILE_PATTERNS}
    for category, patterns in KEY_FILE_PATTERNS.items():
        for pattern in patterns:
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    if f not in result[category]:
                        result[category].append(f)
    return result


def extract_exports(content: str, lang: str) -> list[str]:
    """Extract exported names from source code."""
    exports = []
    if lang in ("TypeScript", "JavaScript"):
        # export function/class/const
        for m in re.finditer(r'export\s+(?:default\s+)?(?:function|class|const|let|var|async\s+function)\s+(\w+)', content):
            exports.append(m.group(1))
    elif lang == "Python":
        for m in re.finditer(r'^(?:class|def|async\s+def)\s+(\w+)', content, re.MULTILINE):
            exports.append(m.group(1))
    elif lang == "Go":
        for m in re.finditer(r'^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)', content, re.MULTILINE):
            exports.append(m.group(1))
    return exports[:20]  # cap


def get_file_info(root: Path, rel_path: str) -> dict:
    """Get summary info for a file."""
    full = root / rel_path
    try:
        content = full.read_text(errors="ignore")
    except Exception:
        return {"path": rel_path, "size": 0, "summary": "(unreadable)"}

    size = len(content)
    ext = os.path.splitext(rel_path)[1]
    ext_map = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go",
        ".rs": "Rust", ".md": "Markdown", ".json": "JSON",
        ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    }
    lang = ext_map.get(ext, "")

    exports = extract_exports(content, lang) if lang else []

    # First meaningful line as summary
    lines = content.strip().splitlines()
    summary = ""
    for line in lines[:10]:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            summary = line.lstrip("#/ ").strip()
            break

    return {
        "path": rel_path,
        "size": size,
        "lines": len(lines),
        "lang": lang,
        "exports": exports,
        "summary": summary,
    }


def build_tree_string(files: list[str], max_items: int = 40) -> str:
    """Build a compact tree string from file list."""
    if not files:
        return "(empty)"
    # Limit
    shown = files[:max_items]
    tree = {}
    for f in shown:
        parts = f.split(os.sep)
        node = tree
        for p in parts[:-1]:
            node = node.setdefault(p + "/", {})
        node[parts[-1]] = None

    def render(node, prefix=""):
        lines = []
        items = list(node.items())
        for i, (name, children) in enumerate(items):
            last = i == len(items) - 1
            connector = "└── " if last else "├── "
            lines.append(f"{prefix}{connector}{name}")
            if children is not None:
                ext = "    " if last else "│   "
                lines.extend(render(children, prefix + ext))
        return lines

    result = render(tree)
    if len(files) > max_items:
        result.append(f"... ({len(files) - max_items} more files)")
    return "\n".join(result)


def read_package_json(root: Path) -> Optional[dict]:
    pkg = root / "package.json"
    if pkg.exists():
        try:
            return json.loads(pkg.read_text(errors="ignore"))
        except Exception:
            pass
    return None


def read_pyproject(root: Path) -> Optional[str]:
    pp = root / "pyproject.toml"
    if pp.exists():
        try:
            return pp.read_text(errors="ignore")
        except Exception:
            pass
    return None


# ── Output Generation ──────────────────────────────────────────────────

def generate_context(
    root: Path,
    files: list[str],
    key_files: dict[str, list[str]],
    languages: list[str],
    frameworks: list[str],
    project_name: str,
    max_tokens: int,
    fmt: str,
) -> str:
    """Generate the context markdown."""
    sections = []
    pkg = read_package_json(root)

    # Header
    header_map = {
        "agents": "# Project Context (AGENTS.md)",
        "claude": "# Project Context (CLAUDE.md)",
        "cursor": "# Project Context (.cursorrules)",
        "generic": "# Project Context",
    }
    sections.append(header_map.get(fmt, header_map["generic"]))
    sections.append(f"Auto-generated by ctxpack v{VERSION}")

    # Overview
    sections.append("\n## Overview")
    desc = ""
    if pkg and pkg.get("description"):
        desc = f"\n{pkg['description']}"
    sections.append(textwrap.dedent(f"""\
    - **Project:** {project_name}{desc}
    - **Languages:** {', '.join(languages) or 'Unknown'}
    - **Frameworks:** {', '.join(frameworks) or 'None detected'}"""))

    # Build/test commands
    sections.append("\n## Commands")
    cmds = []
    if pkg:
        s = pkg.get("scripts", {})
        for name in ["dev", "start", "build", "test", "lint", "format"]:
            if name in s:
                cmds.append(f"- `{name}`: `{s[name]}`")
    pyproject = read_pyproject(root)
    if pyproject:
        if "pytest" in pyproject:
            cmds.append("- `test`: `pytest`")
        if "black" in pyproject:
            cmds.append("- `format`: `black .`")
        if "ruff" in pyproject:
            cmds.append("- `lint`: `ruff check .`")
    # Check Makefile
    if (root / "Makefile").exists():
        cmds.append("- See `Makefile` for available commands")
    if cmds:
        sections.extend(cmds)
    else:
        sections.append("- No standard build commands detected")

    # Structure
    sections.append("\n## Directory Structure")
    sections.append("```")
    sections.append(f"{project_name}/")
    sections.append(build_tree_string(files))
    sections.append("```")

    # Key files by category
    sections.append("\n## Key Files")
    for category, paths in key_files.items():
        if not paths:
            continue
        label = category.replace("_", " ").title()
        sections.append(f"\n### {label}")
        for p in paths[:10]:  # cap per category
            info = get_file_info(root, p)
            line = f"- **`{p}`**"
            details = []
            if info.get("lines"):
                details.append(f"{info['lines']} lines")
            if info.get("exports"):
                details.append(f"exports: {', '.join(info['exports'][:5])}")
            if info.get("summary"):
                details.append(info['summary'][:60])
            if details:
                line += f" — {'; '.join(details)}"
            sections.append(line)

    # Dependencies
    if pkg:
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if deps:
            sections.append("\n## Key Dependencies")
            notable = []
            for name in sorted(deps):
                if name not in ("typescript", "@types/node") and not name.startswith("@types/"):
                    notable.append(f"- {name}: `{deps[name]}`")
            sections.extend(notable[:20])

    # Patterns
    sections.append("\n## Patterns & Conventions")
    patterns = []
    # Detect TypeScript strict mode
    tsconfig = root / "tsconfig.json"
    if tsconfig.exists():
        try:
            tsc = json.loads(tsconfig.read_text(errors="ignore"))
            if tsc.get("compilerOptions", {}).get("strict"):
                patterns.append("- TypeScript strict mode enabled")
        except Exception:
            pass
    # Detect test patterns
    if key_files.get("test"):
        patterns.append("- Tests co-located with source or in dedicated test/ directory")
    if key_files.get("schema"):
        patterns.append("- Schema/type definitions present")
    if patterns:
        sections.extend(patterns)
    else:
        sections.append("- No specific patterns detected")

    result = "\n".join(sections)

    # Token check
    tokens = estimate_tokens(result)
    if tokens > max_tokens:
        eprint(f"⚠️  Warning: Generated context ~{tokens} tokens (limit: {max_tokens})")
        eprint("   Consider increasing --max-tokens or using --include to be more selective")

    return result


# ── Stats Generation ───────────────────────────────────────────────────

def generate_stats(
    root: Path, files: list[str], key_files: dict[str, list[str]],
    languages: list[str], frameworks: list[str], project_name: str,
) -> dict:
    """Generate project statistics as a structured dict."""
    ext_map = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go",
        ".rs": "Rust", ".java": "Java", ".md": "Markdown",
        ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    }
    lang_stats = {}
    total_lines = 0
    total_size = 0

    for f in files:
        ext = os.path.splitext(f)[1]
        lang = ext_map.get(ext, "Other")
        info = get_file_info(root, f)
        lines = info.get("lines", 0)
        size = info.get("size", 0)
        total_lines += lines
        total_size += size
        if lang not in lang_stats:
            lang_stats[lang] = {"files": 0, "lines": 0, "bytes": 0}
        lang_stats[lang]["files"] += 1
        lang_stats[lang]["lines"] += lines
        lang_stats[lang]["bytes"] += size

    # Count exports across all source files
    total_exports = 0
    for f in files:
        ext = os.path.splitext(f)[1]
        lang = ext_map.get(ext, "")
        if lang in ("TypeScript", "JavaScript", "Python", "Go"):
            info = get_file_info(root, f)
            total_exports += len(info.get("exports", []))

    return {
        "project": project_name,
        "totalFiles": len(files),
        "totalLines": total_lines,
        "totalBytes": total_size,
        "languages": lang_stats,
        "frameworks": frameworks,
        "keyFilesByCategory": {k: len(v) for k, v in key_files.items() if v},
        "totalExports": total_exports,
        "estimatedTokens": estimate_tokens(
            "\n".join(get_file_info(root, f).get("summary", "") for f in files[:100])
        ),
    }


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate optimized context files for AI coding agents",
        prog="ctxpack",
    )
    parser.add_argument("path", nargs="?", default=".", help="Project directory (default: .)")
    parser.add_argument("-o", "--output", help="Output file path (default: stdout)")
    parser.add_argument("--format", choices=["agents", "claude", "cursor", "generic"],
                        default="generic", help="Output format (default: generic)")
    parser.add_argument("--max-tokens", type=int, default=8000,
                        help="Max target tokens (default: 8000)")
    parser.add_argument("--include", action="append", default=[],
                        help="Additional glob patterns to include")
    parser.add_argument("--name", help="Project name (default: directory name)")
    parser.add_argument("--stats", action="store_true",
                        help="Output project statistics as JSON instead of context")
    parser.add_argument("-v", "--version", action="version", version=f"ctxpack {VERSION}")

    args = parser.parse_args()
    root = Path(args.path).resolve()

    if not root.is_dir():
        eprint(f"Error: {root} is not a directory")
        sys.exit(1)

    project_name = args.name or root.name
    eprint(f"📂 Scanning {root} ...")

    gitignore = load_gitignore(root)
    files = scan_tree(root, gitignore)
    eprint(f"   Found {len(files)} files")

    languages = detect_languages(files)
    frameworks = detect_frameworks(root, files)
    eprint(f"   Languages: {', '.join(languages) or 'None detected'}")
    eprint(f"   Frameworks: {', '.join(frameworks) or 'None detected'}")

    key_files = find_key_files(files, root)
    total_key = sum(len(v) for v in key_files.values())
    eprint(f"   Key files identified: {total_key}")

    # Add user-included patterns
    if args.include:
        for pat in args.include:
            for f in files:
                if fnmatch.fnmatch(f, pat) and f not in key_files["entry"]:
                    key_files["entry"].append(f)

    if args.stats:
        eprint(f"📊 Generating stats ...")
        stats = generate_stats(
            root=root, files=files, key_files=key_files,
            languages=languages, frameworks=frameworks,
            project_name=project_name,
        )
        output = json.dumps(stats, indent=2)
        if args.output:
            Path(args.output).write_text(output)
            eprint(f"✅ Stats written to {args.output}")
        else:
            print(output)
        return

    eprint(f"🧱 Generating context ({args.format} format) ...")
    context = generate_context(
        root=root,
        files=files,
        key_files=key_files,
        languages=languages,
        frameworks=frameworks,
        project_name=project_name,
        max_tokens=args.max_tokens,
        fmt=args.format,
    )

    tokens = estimate_tokens(context)
    eprint(f"   ~{tokens} tokens, {len(context)} chars")

    if args.output:
        out = Path(args.output)
        out.write_text(context)
        eprint(f"✅ Written to {out}")
    else:
        print(context)


if __name__ == "__main__":
    main()
