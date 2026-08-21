#!/usr/bin/env python3
"""
Project Dashboard Generator

Scans all projects in a workspace and generates a unified health/status dashboard.
Useful for AI agents and developers to quickly understand project status.

Features:
- Git status detection
- Test coverage detection
- Documentation completeness
- Dependency freshness
- TODO/FIXME counts
- Activity tracking (last modified)
- Unified dashboard output (Markdown/JSON)
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ProjectInfo:
    """Information about a single project."""
    name: str
    path: str
    language: str = "unknown"
    has_git: bool = False
    git_status: str = "clean"  # clean, dirty, untracked
    has_tests: bool = False
    test_framework: str = ""
    has_docs: bool = False
    doc_files: list = field(default_factory=list)
    has_readme: bool = False
    has_changelog: bool = False
    todo_count: int = 0
    fixme_count: int = 0
    last_modified: str = ""
    file_count: int = 0
    line_count: int = 0
    dependencies: dict = field(default_factory=dict)
    health_score: int = 0  # 0-100


class ProjectDashboard:
    """Generates dashboard for multiple projects."""
    
    IGNORE_DIRS = {
        'node_modules', '.git', '__pycache__', 'venv', '.venv',
        'dist', 'build', '.next', 'coverage', '.pytest_cache',
        'egg-info', '.mypy_cache', '.tox', 'env'
    }
    
    CODE_EXTENSIONS = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.jsx': 'JavaScript',
        '.tsx': 'TypeScript',
        '.go': 'Go',
        '.rs': 'Rust',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.sh': 'Shell',
        '.md': 'Markdown',
    }
    
    DOC_FILES = {'README.md', 'README.rst', 'README.txt', 'CHANGELOG.md', 'CHANGELOG.txt',
                 'CONTRIBUTING.md', 'API.md', 'TUTORIAL.md', 'USAGE.md'}
    
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path).expanduser().resolve()
        self.projects: list[ProjectInfo] = []
    
    def scan(self) -> list[ProjectInfo]:
        """Scan all projects in the workspace."""
        for item in self.workspace.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                if self._is_project(item):
                    project = self._analyze_project(item)
                    self.projects.append(project)
        
        # Sort by health score (descending)
        self.projects.sort(key=lambda p: p.health_score, reverse=True)
        return self.projects
    
    def _is_project(self, path: Path) -> bool:
        """Check if a directory is a project."""
        # Has package.json, requirements.txt, Cargo.toml, go.mod, etc.
        indicators = [
            'package.json', 'requirements.txt', 'Cargo.toml', 'go.mod',
            'pom.xml', 'build.gradle', 'Gemfile', 'composer.json',
            'setup.py', 'pyproject.toml', '.git', 'Makefile'
        ]
        return any((path / ind).exists() for ind in indicators)
    
    def _analyze_project(self, path: Path) -> ProjectInfo:
        """Analyze a single project."""
        project = ProjectInfo(name=path.name, path=str(path))
        
        # Detect language
        project.language = self._detect_language(path)
        
        # Git status
        project.has_git = (path / '.git').exists()
        if project.has_git:
            project.git_status = self._get_git_status(path)
        
        # Tests
        project.has_tests, project.test_framework = self._detect_tests(path)
        
        # Documentation
        project.doc_files = [f.name for f in path.iterdir() if f.name in self.DOC_FILES and f.is_file()]
        project.has_readme = 'README.md' in project.doc_files or 'README.rst' in project.doc_files
        project.has_changelog = 'CHANGELOG.md' in project.doc_files or 'CHANGELOG.txt' in project.doc_files
        project.has_docs = len(project.doc_files) > 0
        
        # TODO/FIXME counts
        project.todo_count, project.fixme_count = self._count_todos(path)
        
        # File stats
        project.file_count, project.line_count, project.last_modified = self._get_file_stats(path)
        
        # Dependencies
        project.dependencies = self._get_dependencies(path)
        
        # Calculate health score
        project.health_score = self._calculate_health_score(project)
        
        return project
    
    def _detect_language(self, path: Path) -> str:
        """Detect primary programming language."""
        lang_count = {}
        
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in self.CODE_EXTENSIONS:
                    lang = self.CODE_EXTENSIONS[ext]
                    lang_count[lang] = lang_count.get(lang, 0) + 1
        
        if lang_count:
            return max(lang_count, key=lang_count.get)
        return "unknown"
    
    def _get_git_status(self, path: Path) -> str:
        """Get git status of a project."""
        try:
            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if not lines or lines == ['']:
                    return "clean"
                
                for line in lines:
                    if line.strip():
                        status = line[:2]
                        if 'M' in status or 'A' in status or 'D' in status:
                            return "dirty"
                return "untracked"
        except (subprocess.TimeoutExpired, Exception):
            pass
        
        return "unknown"
    
    def _detect_tests(self, path: Path) -> tuple[bool, str]:
        """Detect test framework.

        A file that merely exists (pyproject.toml, Cargo.toml, go.mod)
        does NOT prove tests are wired up — verify actual test evidence
        before awarding has_tests (worth 25 health points).
        """
        # Config files that by themselves prove a test framework is set up
        test_indicators = {
            'pytest': ['pytest.ini', 'conftest.py'],
            'jest': ['jest.config.js', 'jest.config.ts', 'jest.config.cjs'],
            'mocha': ['.mocharc.js', '.mocharc.json'],
            'vitest': ['vitest.config.ts', 'vitest.config.js'],
        }

        for framework, indicators in test_indicators.items():
            for ind in indicators:
                if (path / ind).exists():
                    return True, framework

        # pyproject.toml only counts when pytest is actually configured inside
        pyproject = path / 'pyproject.toml'
        if pyproject.exists():
            try:
                if 'pytest' in pyproject.read_text(encoding='utf-8', errors='ignore'):
                    return True, 'pytest'
            except Exception:
                pass

        # Cargo: only when a tests/ directory exists alongside
        if (path / 'Cargo.toml').exists() and (path / 'tests').is_dir():
            return True, 'cargo'

        # Go: only when at least one *_test.go file exists
        if self._has_go_tests(path):
            return True, 'go'

        # Generic test directories
        test_dirs = ['tests', 'test', '__tests__', 'spec']
        for td in test_dirs:
            if (path / td).is_dir():
                return True, "generic"

        return False, ""

    def _has_go_tests(self, path: Path) -> bool:
        """Check for any *_test.go file (respecting IGNORE_DIRS)."""
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            if any(f.endswith('_test.go') for f in files):
                return True
        return False
    
    def _count_todos(self, path: Path) -> tuple[int, int]:
        """Count TODO and FIXME comments."""
        todo_count = 0
        fixme_count = 0
        
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in self.CODE_EXTENSIONS:
                    try:
                        with open(Path(root) / file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            todo_count += content.upper().count('TODO')
                            fixme_count += content.upper().count('FIXME')
                    except Exception:
                        pass
        
        return todo_count, fixme_count
    
    def _get_file_stats(self, path: Path) -> tuple[int, int, str]:
        """Get file count, line count, and last modified date."""
        file_count = 0
        line_count = 0
        last_modified = ""
        
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in self.CODE_EXTENSIONS:
                    file_count += 1
                    try:
                        file_path = Path(root) / file
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            line_count += len(f.readlines())
                        
                        # Track last modified
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if not last_modified or mtime > datetime.fromisoformat(last_modified):
                            last_modified = mtime.isoformat()
                    except Exception:
                        pass
        
        return file_count, line_count, last_modified
    
    def _get_dependencies(self, path: Path) -> dict:
        """Get dependency info."""
        deps = {}
        
        # package.json
        pkg_json = path / 'package.json'
        if pkg_json.exists():
            try:
                with open(pkg_json) as f:
                    data = json.load(f)
                    deps['npm'] = {
                        'dependencies': len(data.get('dependencies', {})),
                        'devDependencies': len(data.get('devDependencies', {}))
                    }
            except Exception:
                pass
        
        # requirements.txt
        req_txt = path / 'requirements.txt'
        if req_txt.exists():
            try:
                with open(req_txt) as f:
                    lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                    deps['pip'] = {'count': len(lines)}
            except Exception:
                pass
        
        # Cargo.toml
        cargo_toml = path / 'Cargo.toml'
        if cargo_toml.exists():
            deps['cargo'] = {'exists': True}
        
        # go.mod
        go_mod = path / 'go.mod'
        if go_mod.exists():
            deps['go'] = {'exists': True}
        
        return deps
    
    def _calculate_health_score(self, project: ProjectInfo) -> int:
        """Calculate health score (0-100)."""
        score = 0
        
        # Documentation (30 points)
        if project.has_readme:
            score += 15
        if project.has_changelog:
            score += 10
        if len(project.doc_files) >= 3:
            score += 5
        
        # Testing (25 points)
        if project.has_tests:
            score += 25
        
        # Git status (20 points)
        if project.has_git:
            if project.git_status == "clean":
                score += 20
            elif project.git_status == "untracked":
                score += 10
        
        # Code quality (15 points)
        if project.todo_count + project.fixme_count == 0:
            score += 15
        elif project.todo_count + project.fixme_count < 10:
            score += 10
        elif project.todo_count + project.fixme_count < 50:
            score += 5
        
        # Activity (10 points)
        if project.last_modified:
            try:
                last_mod = datetime.fromisoformat(project.last_modified)
                days_ago = (datetime.now() - last_mod).days
                if days_ago < 7:
                    score += 10
                elif days_ago < 30:
                    score += 5
            except Exception:
                pass
        
        return min(100, max(0, score))
    
    def generate_markdown(self) -> str:
        """Generate Markdown dashboard."""
        lines = [
            "# 📊 Project Dashboard",
            f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
            f"**Total Projects**: {len(self.projects)}\n",
            "## Overview\n",
        ]
        
        # Summary stats
        total_files = sum(p.file_count for p in self.projects)
        total_lines = sum(p.line_count for p in self.projects)
        with_tests = sum(1 for p in self.projects if p.has_tests)
        with_docs = sum(1 for p in self.projects if p.has_docs)
        
        lines.extend([
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Files | {total_files:,} |",
            f"| Total Lines | {total_lines:,} |",
            f"| Projects with Tests | {with_tests}/{len(self.projects)} |",
            f"| Projects with Docs | {with_docs}/{len(self.projects)} |",
            f"| Avg Health Score | {sum(p.health_score for p in self.projects) // max(len(self.projects), 1):.0f} |",
            "",
        ])
        
        # Project table
        lines.extend([
            "## Projects\n",
            "| Project | Language | Health | Git | Tests | Docs | TODOs | Files | Lines |",
            "|---------|----------|--------|-----|-------|------|-------|-------|-------|",
        ])
        
        for p in self.projects:
            health_emoji = "🟢" if p.health_score >= 70 else "🟡" if p.health_score >= 40 else "🔴"
            git_emoji = "✅" if p.git_status == "clean" else "⚠️" if p.git_status == "dirty" else "📝"
            tests_emoji = "✅" if p.has_tests else "❌"
            docs_emoji = "📚" if p.has_docs else "📄"
            
            lines.append(
                f"| {p.name} | {p.language} | {health_emoji} {p.health_score} | "
                f"{git_emoji} | {tests_emoji} | {docs_emoji} | {p.todo_count} | "
                f"{p.file_count:,} | {p.line_count:,} |"
            )
        
        lines.append("")
        
        # Needs attention
        needs_attention = [p for p in self.projects if p.health_score < 50]
        if needs_attention:
            lines.extend([
                "## ⚠️ Needs Attention\n",
                "| Project | Issues |",
                "|---------|--------|",
            ])
            
            for p in needs_attention:
                issues = []
                if not p.has_tests:
                    issues.append("no tests")
                if not p.has_docs:
                    issues.append("no docs")
                if p.git_status == "dirty":
                    issues.append("uncommitted changes")
                if p.todo_count + p.fixme_count > 10:
                    issues.append(f"{p.todo_count + p.fixme_count} TODOs")
                
                lines.append(f"| {p.name} | {', '.join(issues) or 'low score'} |")
            
            lines.append("")
        
        # Recently active
        recent = sorted(
            [p for p in self.projects if p.last_modified],
            key=lambda p: p.last_modified,
            reverse=True
        )[:5]
        
        if recent:
            lines.extend([
                "## 🕒 Recently Active\n",
            ])
            
            for p in recent:
                try:
                    dt = datetime.fromisoformat(p.last_modified)
                    days_ago = (datetime.now() - dt).days
                    time_str = f"{days_ago}d ago" if days_ago > 0 else "today"
                except Exception:
                    time_str = "unknown"
                
                lines.append(f"- **{p.name}** ({time_str})")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_json(self) -> str:
        """Generate JSON dashboard."""
        data = {
            "generated": datetime.now().isoformat(),
            "summary": {
                "total_projects": len(self.projects),
                "total_files": sum(p.file_count for p in self.projects),
                "total_lines": sum(p.line_count for p in self.projects),
                "avg_health_score": sum(p.health_score for p in self.projects) // max(len(self.projects), 1),
                "with_tests": sum(1 for p in self.projects if p.has_tests),
                "with_docs": sum(1 for p in self.projects if p.has_docs),
            },
            "projects": [
                {
                    "name": p.name,
                    "path": p.path,
                    "language": p.language,
                    "health_score": p.health_score,
                    "has_git": p.has_git,
                    "git_status": p.git_status,
                    "has_tests": p.has_tests,
                    "test_framework": p.test_framework,
                    "has_docs": p.has_docs,
                    "doc_files": p.doc_files,
                    "todo_count": p.todo_count,
                    "fixme_count": p.fixme_count,
                    "file_count": p.file_count,
                    "line_count": p.line_count,
                    "last_modified": p.last_modified,
                    "dependencies": p.dependencies,
                }
                for p in self.projects
            ]
        }
        
        return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a unified dashboard for all projects in a workspace"
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Path to workspace directory (default: current directory)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--min-health",
        type=int,
        default=0,
        help="Only show projects with health score >= this value"
    )
    
    args = parser.parse_args()
    
    dashboard = ProjectDashboard(args.workspace)
    if not dashboard.workspace.is_dir():
        print(f"Error: workspace not found: {dashboard.workspace}", file=sys.stderr)
        sys.exit(1)
    projects = dashboard.scan()
    
    # Filter by minimum health score
    dashboard.projects = [p for p in projects if p.health_score >= args.min_health]
    
    # Generate output
    if args.format == "json":
        output = dashboard.generate_json()
    else:
        output = dashboard.generate_markdown()
    
    # Write or print
    if args.output:
        Path(args.output).write_text(output)
        print(f"Dashboard written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
