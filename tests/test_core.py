"""
tests/test_core.py — Basic tests for TokenWise core tools.
Run: pytest tests/ -v
"""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTokenCounter:
    def test_imports(self):
        from core.token_counter import estimate_tokens, scan_directory, format_number
        assert callable(estimate_tokens)
        assert callable(scan_directory)
        assert callable(format_number)

    def test_estimate_tokens_basic(self):
        from core.token_counter import estimate_tokens
        tokens = estimate_tokens("Hello, world!", "generic")
        assert tokens > 0
        assert tokens < 10

    def test_estimate_tokens_scales(self):
        from core.token_counter import estimate_tokens
        short = estimate_tokens("Hello", "generic")
        long  = estimate_tokens("Hello " * 100, "generic")
        assert long > short

    def test_format_number(self):
        from core.token_counter import format_number
        assert format_number(500) == "500"
        assert "k" in format_number(1500)
        assert "M" in format_number(1_500_000)

    def test_scan_directory(self):
        from core.token_counter import scan_directory
        results = scan_directory(Path("."), "generic", respect_llmignore=False)
        assert isinstance(results, list)
        if results:
            r = results[0]
            assert "path" in r
            assert "tokens" in r
            assert "lines" in r
            assert r["tokens"] > 0

    def test_scan_skips_binary(self):
        from core.token_counter import scan_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "code.py").write_text("x = 1\n" * 50)
            (p / "image.png").write_bytes(b"\x89PNG\r\n")
            results = scan_directory(p, "generic", respect_llmignore=False)
            paths = [r["path"] for r in results]
            assert any("code.py" in p for p in paths)
            assert not any("image.png" in p for p in paths)

    def test_llmignore_respected(self):
        from core.token_counter import scan_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "keep.py").write_text("x = 1\n" * 20)
            (p / "skip.py").write_text("y = 2\n" * 20)
            (p / ".llmignore").write_text("skip.py\n")
            all_results  = scan_directory(p, "generic", respect_llmignore=False)
            with_ignore   = scan_directory(p, "generic", respect_llmignore=True)
            all_paths     = [r["path"] for r in all_results]
            ignore_paths  = [r["path"] for r in with_ignore]
            assert any("keep.py" in x for x in all_paths)
            assert any("skip.py" in x for x in all_paths)
            assert any("keep.py" in x for x in ignore_paths)
            assert not any("skip.py" in x for x in ignore_paths)


class TestContextAnalyzer:
    def test_imports(self):
        from core.context_analyzer import analyze_directory, WastePattern
        assert callable(analyze_directory)

    def test_detects_lock_files(self):
        from core.context_analyzer import analyze_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            # Create a fake large lock file
            (p / "package-lock.json").write_text('{"name": "test"}\n' * 200)
            patterns = analyze_directory(p, "generic")
            names = [pat.name for pat in patterns]
            assert any("Lock" in n or "lock" in n.lower() for n in names)

    def test_pattern_has_required_fields(self):
        from core.context_analyzer import analyze_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "package-lock.json").write_text("x" * 5000)
            patterns = analyze_directory(p, "generic")
            for pat in patterns:
                assert hasattr(pat, "name")
                assert hasattr(pat, "severity")
                assert hasattr(pat, "fix")
                assert pat.severity in ("high", "medium", "low")


class TestGenerateConfig:
    def test_detect_node_project(self):
        from scripts.generate_config import detect_project
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "package.json").write_text('{"name": "test", "dependencies": {}}')
            info = detect_project(p)
            assert info["language"] == "javascript/typescript"

    def test_detect_python_project(self):
        from scripts.generate_config import detect_project
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "requirements.txt").write_text("flask\n")
            info = detect_project(p)
            assert info["language"] == "python"

    def test_generate_claude_md_lean(self):
        from scripts.generate_config import generate_claude_md
        info = {
            "type": "node", "language": "javascript/typescript",
            "pkg_manager": "pnpm", "test_cmd": "pnpm test",
            "lint_cmd": "pnpm typecheck", "src_dirs": ["src"],
            "forbidden_dirs": ["node_modules", "dist"]
        }
        result = generate_claude_md(info)
        lines = result.split("\n")
        assert len(lines) < 40, f"CLAUDE.md too long: {len(lines)} lines"
        assert "pnpm test" in result
        assert "node_modules" in result

    def test_generate_llmignore_has_node_modules(self):
        from scripts.generate_config import generate_llmignore
        info = {"type": "node", "language": "js"}
        result = generate_llmignore(info)
        assert "node_modules" in result
        assert "package-lock.json" in result
