"""Tests for ctxpack — context file generator for AI coding agents."""

import json
import os
import tempfile

import pytest

# Add parent dir to path
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctxpack import (
    build_tree_string,
    detect_frameworks,
    detect_languages,
    estimate_tokens,
    extract_exports,
    find_key_files,
    get_file_info,
    load_gitignore,
    should_ignore,
    truncate,
)


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project structure."""
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "test-project",
                "description": "A test project",
                "scripts": {"dev": "vite", "build": "tsc", "test": "vitest"},
                "dependencies": {"react": "^18.0.0"},
                "devDependencies": {"typescript": "^5.0.0", "vitest": "^1.0.0"},
            }
        )
    )
    (tmp_path / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"strict": True, "target": "ES2022"}})
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.ts").write_text(
        "export function main(): void { console.log('hello'); }\n"
    )
    (src / "utils.ts").write_text(
        "export const helper = (x: number) => x * 2;\n"
        "export function greet(name: string): string { return `Hello ${name}`; }\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "index.test.ts").write_text(
        'import { main } from "../src/index";\ntest("main", () => { main(); });\n'
    )
    (tmp_path / "README.md").write_text("# Test Project\nA description.\n")
    (tmp_path / ".gitignore").write_text("node_modules/\ndist/\n*.log\n")
    return tmp_path


@pytest.fixture
def python_project(tmp_path):
    """Create a minimal Python project."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'myapp'\ndependencies = ['fastapi', 'uvicorn']\n\n"
        "[tool.pytest]\n"
    )
    (tmp_path / "app.py").write_text(
        'from fastapi import FastAPI\napp = FastAPI()\n\n@app.get("/")\ndef read_root():\n    return {"hello": "world"}\n'
    )
    (tmp_path / "models.py").write_text(
        "class User:\n    def __init__(self, name: str):\n        self.name = name\n\n"
        "async def fetch_user(user_id: int):\n    pass\n"
    )
    return tmp_path


# ── Unit Tests ─────────────────────────────────────────────────────────


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_basic(self):
        # 4 chars per token
        assert estimate_tokens("abcd") == 1
        assert estimate_tokens("abcdefgh") == 2

    def test_unicode(self):
        assert estimate_tokens("你好世界") >= 1


class TestTruncate:
    def test_short_string_unchanged(self):
        assert truncate("hello") == "hello"

    def test_long_string_truncated(self):
        long = "x" * 10000
        result = truncate(long, max_len=100)
        assert result.endswith("... (truncated)")
        assert len(result) < 200

    def test_exact_length(self):
        s = "x" * 100
        assert truncate(s, max_len=100) == s


class TestShouldIgnore:
    def test_node_modules(self):
        assert should_ignore("node_modules", set())

    def test_git_dir(self):
        assert should_ignore(".git", set())

    def test_lock_file(self):
        assert should_ignore("package-lock.json", set())

    def test_normal_file(self):
        assert not should_ignore("index.ts", set())

    def test_gitignore_pattern(self):
        # gitignore patterns are matched against full relative path
        assert should_ignore("build", {"build/"})

    def test_nested_ignored_dir(self):
        # The name "node_modules" is matched, not the full path
        assert should_ignore(os.path.join("src", "node_modules"), set())


class TestDetectLanguages:
    def test_typescript_project(self):
        files = ["src/index.ts", "src/utils.ts", "README.md"]
        langs = detect_languages(files)
        assert "TypeScript" in langs
        assert len(langs) == 1

    def test_mixed_languages(self):
        files = ["app.py", "index.js", "main.go", "style.css"]
        langs = detect_languages(files)
        assert "Python" in langs
        assert "JavaScript" in langs
        assert "Go" in langs

    def test_no_code_files(self):
        files = ["README.md", "package.json", ".gitignore"]
        assert detect_languages(files) == []


class TestDetectFrameworks:
    def test_react_from_package_json(self, project_dir):
        files = ["package.json"]
        frameworks = detect_frameworks(project_dir, files)
        assert "react" in frameworks

    def test_fastapi_from_pyproject(self, python_project):
        files = ["pyproject.toml"]
        frameworks = detect_frameworks(python_project, files)
        assert "fastapi" in frameworks

    def test_no_framework(self, tmp_path):
        (tmp_path / "main.c").write_text('int main() { return 0; }')
        assert detect_frameworks(tmp_path, ["main.c"]) == []


class TestExtractExports:
    def test_typescript_exports(self):
        code = "export function hello() {}\nexport const x = 1;\nexport class Foo {}"
        exports = extract_exports(code, "TypeScript")
        assert "hello" in exports
        assert "x" in exports
        assert "Foo" in exports

    def test_python_exports(self):
        code = "class MyClass:\n    pass\n\ndef my_func():\n    pass\n\nasync def async_func():\n    pass"
        exports = extract_exports(code, "Python")
        assert "MyClass" in exports
        assert "my_func" in exports
        assert "async_func" in exports

    def test_go_exports(self):
        code = "func HelloWorld() {}\nfunc (s *Server) Start() {}"
        exports = extract_exports(code, "Go")
        assert "HelloWorld" in exports
        assert "Start" in exports


class TestBuildTreeString:
    def test_empty(self):
        assert build_tree_string([]) == "(empty)"

    def test_simple_files(self):
        result = build_tree_string(["a.txt", "b.txt"])
        assert "a.txt" in result
        assert "b.txt" in result

    def test_nested_structure(self):
        result = build_tree_string(["src/index.ts", "src/utils.ts", "README.md"])
        assert "src/" in result
        assert "index.ts" in result

    def test_truncation(self):
        files = [f"file_{i}.txt" for i in range(50)]
        result = build_tree_string(files, max_items=10)
        assert "more files" in result


class TestLoadGitignore:
    def test_with_gitignore(self, project_dir):
        patterns = load_gitignore(project_dir)
        assert "node_modules/" in patterns
        assert "dist/" in patterns

    def test_without_gitignore(self, tmp_path):
        patterns = load_gitignore(tmp_path)
        assert patterns == set()


class TestFindKeyFiles:
    def test_finds_readme(self):
        files = ["README.md", "src/index.ts"]
        result = find_key_files(files, None)
        assert "README.md" in result["docs"]

    def test_finds_config(self):
        files = ["package.json", "tsconfig.json"]
        result = find_key_files(files, None)
        assert "package.json" in result["config"]

    def test_finds_tests(self):
        files = ["tests/index.test.ts", "src/foo.test.ts"]
        result = find_key_files(files, None)
        assert len(result["test"]) >= 1


class TestGetFileInfo:
    def test_typescript_file(self, project_dir):
        info = get_file_info(project_dir, "src/index.ts")
        assert info["lang"] == "TypeScript"
        assert "main" in info["exports"]

    def test_markdown_file(self, project_dir):
        info = get_file_info(project_dir, "README.md")
        assert info["lang"] == "Markdown"
        assert info["lines"] > 0

    def test_unreadable_file(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(bytes(range(256)))
        info = get_file_info(tmp_path, "binary.bin")
        # Should not crash


# ── Integration Tests ──────────────────────────────────────────────────


class TestScanAndGenerate:
    """Test the full pipeline: scan → detect → generate."""

    def test_scan_project(self, project_dir):
        from ctxpack import scan_tree

        gitignore = load_gitignore(project_dir)
        files = scan_tree(project_dir, gitignore)
        # Should find our files but not node_modules
        assert "package.json" in files
        assert "src/index.ts" in files
        assert "src/utils.ts" in files
        assert not any("node_modules" in f for f in files)

    def test_generate_context_typescript(self, project_dir):
        from ctxpack import generate_context, scan_tree

        gitignore = load_gitignore(project_dir)
        files = scan_tree(project_dir, gitignore)
        langs = detect_languages(files)
        frameworks = detect_frameworks(project_dir, files)
        key_files = find_key_files(files, project_dir)

        result = generate_context(
            root=project_dir,
            files=files,
            key_files=key_files,
            languages=langs,
            frameworks=frameworks,
            project_name="test-project",
            max_tokens=8000,
            fmt="generic",
        )

        assert "# Project Context" in result
        assert "TypeScript" in result
        assert "react" in result
        assert "test-project" in result
        # src/index.ts appears in tree as "index.ts" under src/
        assert "index.ts" in result

    def test_generate_agents_format(self, project_dir):
        from ctxpack import generate_context, scan_tree

        gitignore = load_gitignore(project_dir)
        files = scan_tree(project_dir, gitignore)
        langs = detect_languages(files)
        frameworks = detect_frameworks(project_dir, files)
        key_files = find_key_files(files, project_dir)

        result = generate_context(
            root=project_dir,
            files=files,
            key_files=key_files,
            languages=langs,
            frameworks=frameworks,
            project_name="test-project",
            max_tokens=8000,
            fmt="agents",
        )
        assert "AGENTS.md" in result

    def test_python_project(self, python_project):
        from ctxpack import generate_context, scan_tree

        gitignore = load_gitignore(python_project)
        files = scan_tree(python_project, gitignore)
        langs = detect_languages(files)
        frameworks = detect_frameworks(python_project, files)
        key_files = find_key_files(files, python_project)

        result = generate_context(
            root=python_project,
            files=files,
            key_files=key_files,
            languages=langs,
            frameworks=frameworks,
            project_name="myapp",
            max_tokens=8000,
            fmt="generic",
        )
        assert "Python" in result
        assert "fastapi" in result
        assert "myapp" in result


class TestGenerateStats:
    def test_stats_typescript_project(self, project_dir):
        from ctxpack import generate_stats, scan_tree

        gitignore = load_gitignore(project_dir)
        files = scan_tree(project_dir, gitignore)
        langs = detect_languages(files)
        frameworks = detect_frameworks(project_dir, files)
        key_files = find_key_files(files, project_dir)

        stats = generate_stats(
            root=project_dir, files=files, key_files=key_files,
            languages=langs, frameworks=frameworks,
            project_name="test-project",
        )

        assert stats["project"] == "test-project"
        assert stats["totalFiles"] > 0
        assert stats["totalLines"] > 0
        assert stats["totalBytes"] > 0
        assert "TypeScript" in stats["languages"]
        assert "react" in stats["frameworks"]
        assert stats["totalExports"] > 0  # main, helper, greet
        assert "config" in stats["keyFilesByCategory"]

    def test_stats_python_project(self, python_project):
        from ctxpack import generate_stats, scan_tree

        gitignore = load_gitignore(python_project)
        files = scan_tree(python_project, gitignore)
        langs = detect_languages(files)
        frameworks = detect_frameworks(python_project, files)
        key_files = find_key_files(files, python_project)

        stats = generate_stats(
            root=python_project, files=files, key_files=key_files,
            languages=langs, frameworks=frameworks,
            project_name="myapp",
        )

        assert stats["totalFiles"] >= 2
        assert "Python" in stats["languages"]
        assert "fastapi" in stats["frameworks"]
        # Python exports: User, fetch_user, app routes
        assert stats["totalExports"] >= 2

    def test_stats_empty_project(self, tmp_path):
        from ctxpack import generate_stats

        stats = generate_stats(
            root=tmp_path, files=[], key_files={},
            languages=[], frameworks=[],
            project_name="empty",
        )
        assert stats["totalFiles"] == 0
        assert stats["totalLines"] == 0
        assert stats["totalExports"] == 0
