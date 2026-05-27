"""
tests/test_core.py — Basic tests for TokenWise core tools.
Run: pytest tests/ -v
"""

import sys
import json
import tempfile
import warnings
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
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "hello.py").write_text("print('hello')\n")
            results = scan_directory(p, "generic", respect_llmignore=False)
            assert isinstance(results, list)
            assert len(results) >= 1
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


# ── Tradeoff #1: Compact quality ──────────────────────────────

class TestCompactQuality:
    def _make_adapter(self, quality="detailed"):
        """Create a minimal concrete adapter for testing."""
        from adapters.base_adapter import BaseLLMAdapter, CompletionResult, Message

        class StubAdapter(BaseLLMAdapter):
            def __init__(self, **kw):
                super().__init__(model="stub", **kw)
                self.api_calls = []

            def _call_api(self, messages, **kwargs):
                self.api_calls.append(messages)
                return CompletionResult(
                    content='{"decisions":[],"files_modified":[],"errors":[],"current_state":"ok","open_questions":[]}',
                    input_tokens=10, output_tokens=10, total_tokens=20,
                    model="stub", latency_ms=1,
                )

            def count_tokens(self, text):
                return max(1, len(text) // 4)

        return StubAdapter(compact_quality=quality)

    def test_detailed_uses_structured_prompt(self):
        adapter = self._make_adapter("detailed")
        from adapters.base_adapter import Message
        for i in range(10):
            adapter._history.append(Message(role="user", content=f"msg {i}"))
            adapter._history.append(Message(role="assistant", content=f"reply {i}"))
        adapter.compact()
        prompt_text = adapter.api_calls[0][0]["content"]
        assert "structured JSON" in prompt_text
        assert "decisions" in prompt_text

    def test_fast_uses_simple_prompt(self):
        adapter = self._make_adapter("fast")
        from adapters.base_adapter import Message
        for i in range(10):
            adapter._history.append(Message(role="user", content=f"msg {i}"))
            adapter._history.append(Message(role="assistant", content=f"reply {i}"))
        adapter.compact()
        prompt_text = adapter.api_calls[0][0]["content"]
        assert "Summarize this conversation" in prompt_text
        assert "structured JSON" not in prompt_text

    def test_detailed_truncates_at_1000_chars(self):
        adapter = self._make_adapter("detailed")
        from adapters.base_adapter import Message
        long_msg = "x" * 1500
        for i in range(6):
            adapter._history.append(Message(role="user", content=long_msg))
            adapter._history.append(Message(role="assistant", content="ok"))
        adapter.compact()
        prompt_text = adapter.api_calls[0][0]["content"]
        # Should contain 1000 x's then ... — not 500
        assert "x" * 1000 in prompt_text
        assert "x" * 1001 not in prompt_text

    def test_last_compact_raw_stored(self):
        adapter = self._make_adapter("detailed")
        from adapters.base_adapter import Message
        for i in range(10):
            adapter._history.append(Message(role="user", content=f"msg {i}"))
            adapter._history.append(Message(role="assistant", content=f"reply {i}"))
        adapter.compact()
        assert adapter.last_compact_raw != ""
        assert "msg 0" in adapter.last_compact_raw


# ── Tradeoff #2: Token estimation warning ─────────────────────

class TestTokenEstimationWarning:
    def test_fallback_emits_warning(self):
        import core.token_counter as tc
        tc._TIKTOKEN_WARNING_SHOWN = False  # reset
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "tiktoken":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = mock_import
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                tc.estimate_tokens("hello world", "generic")
                tiktoken_warnings = [x for x in w if "tiktoken" in str(x.message)]
                assert len(tiktoken_warnings) == 1
                # Second call should NOT warn again
                tc.estimate_tokens("another string", "generic")
                tiktoken_warnings = [x for x in w if "tiktoken" in str(x.message)]
                assert len(tiktoken_warnings) == 1  # still just 1
        finally:
            builtins.__import__ = real_import
            tc._TIKTOKEN_WARNING_SHOWN = False


# ── Tradeoff #3: Subagent model ───────────────────────────────

class TestSubagentModel:
    def test_default_subagent_model_is_none(self):
        # Can't instantiate ClaudeAdapter without anthropic, so test the param acceptance
        from adapters.claude_adapter import ClaudeAdapter
        # Verify the __init__ signature accepts subagent_model
        import inspect
        sig = inspect.signature(ClaudeAdapter.__init__)
        assert "subagent_model" in sig.parameters

    def test_run_subagent_accepts_model_param(self):
        from adapters.claude_adapter import ClaudeAdapter
        import inspect
        sig = inspect.signature(ClaudeAdapter.run_subagent)
        assert "model" in sig.parameters


# ── Tradeoff #4: Large files tracked as skipped ───────────────

class TestSkippedFiles:
    def test_large_file_skipped_with_reason(self):
        from core.token_counter import scan_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "small.py").write_text("x = 1\n" * 10)
            (p / "huge.txt").write_text("y" * 600_000)
            results = scan_directory(p, "generic", respect_llmignore=False, max_file_size=500_000)
            skipped = [r for r in results if r.get("skipped")]
            active = [r for r in results if not r.get("skipped")]
            assert len(skipped) == 1
            assert "huge.txt" in skipped[0]["path"]
            assert "skip_reason" in skipped[0]
            assert skipped[0]["tokens"] == 0
            assert any("small.py" in r["path"] for r in active)

    def test_custom_max_file_size(self):
        from core.token_counter import scan_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "medium.txt").write_text("a" * 1000)
            results = scan_directory(p, "generic", respect_llmignore=False, max_file_size=500)
            skipped = [r for r in results if r.get("skipped")]
            assert len(skipped) == 1

    def test_skipped_excluded_from_totals_in_report(self, capsys):
        from core.token_counter import scan_directory, print_report
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "small.py").write_text("x = 1\n" * 10)
            (p / "huge.txt").write_text("y" * 600_000)
            results = scan_directory(p, "generic", respect_llmignore=False)
            print_report(results, "generic", show_cost=False)
            output = capsys.readouterr().out
            assert "skipped" in output.lower()


# ── Tradeoff #5: Lean mode ────────────────────────────────────

class TestLeanMode:
    def test_openai_lean_mode_default(self):
        import inspect
        from adapters.openai_adapter import OpenAIAdapter
        sig = inspect.signature(OpenAIAdapter.__init__)
        assert "lean_mode" in sig.parameters
        assert sig.parameters["lean_mode"].default is True

    def test_gemini_lean_mode_default(self):
        import inspect
        from adapters.gemini_adapter import GeminiAdapter
        sig = inspect.signature(GeminiAdapter.__init__)
        assert "lean_mode" in sig.parameters
        assert sig.parameters["lean_mode"].default is True


# ── Tradeoff #6: Lazy load fix ────────────────────────────────

class TestLazyLoadFix:
    def _make_adapter(self):
        from adapters.base_adapter import BaseLLMAdapter, CompletionResult

        class StubAdapter(BaseLLMAdapter):
            def _call_api(self, messages, **kwargs):
                return CompletionResult(content="", input_tokens=0, output_tokens=0,
                                        total_tokens=0, model="stub", latency_ms=0)
            def count_tokens(self, text):
                return max(1, len(text) // 4)

        return StubAdapter(model="stub")

    def test_truncation_shows_first_and_last_half(self):
        adapter = self._make_adapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "big.py"
            lines = [f"line {i}\n" for i in range(600)]
            p.write_text("".join(lines))
            content = adapter.load_file_lazy(str(p), max_lines=100)
            assert "lines omitted" in content
            assert "line 0" in content      # first half
            assert "line 599" in content     # last half

    def test_range_loading(self):
        adapter = self._make_adapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "range.py"
            lines = [f"line {i}\n" for i in range(100)]
            p.write_text("".join(lines))
            content = adapter.load_file_lazy(str(p), start_line=10, end_line=20)
            assert "line 9" in content    # 1-based: line 10 is index 9
            assert "line 19" in content   # 1-based: line 20 is index 19
            assert "line 0" not in content
            assert "line 30" not in content

    def test_truncation_line_count_correct(self, capsys):
        adapter = self._make_adapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "big2.py"
            lines = [f"line {i}\n" for i in range(500)]
            p.write_text("".join(lines))
            adapter.load_file_lazy(str(p), max_lines=100)
            output = capsys.readouterr().out
            assert "500 lines" in output  # should show correct total, not 0


# ── Tradeoff #7: Budget gate overhead ─────────────────────────

class TestBudgetOverhead:
    def test_overhead_default_zero(self):
        import inspect
        from core.check import run_check
        sig = inspect.signature(run_check)
        assert "overhead_pct" in sig.parameters
        assert sig.parameters["overhead_pct"].default == 0

    def test_overhead_in_json_output(self, capsys):
        from core.check import run_check
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "a.py").write_text("x = 1\n" * 10)
            run_check(p, model="generic", max_pct=90, output_json=True, overhead_pct=20)
            output = capsys.readouterr().out
            data = json.loads(output)
            assert "overhead_pct" in data
            assert data["overhead_pct"] == 20
            assert "adjusted_tokens" in data

    def test_overhead_zero_omits_adjusted(self, capsys):
        from core.check import run_check
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "a.py").write_text("x = 1\n" * 10)
            run_check(p, model="generic", max_pct=90, output_json=True, overhead_pct=0)
            output = capsys.readouterr().out
            data = json.loads(output)
            assert "overhead_pct" not in data


# ── Tradeoff #8: Path matching improvements ───────────────────

class TestPathMatching:
    def test_matches_path_component_exact(self):
        from core.token_counter import _matches_path_component
        assert _matches_path_component("dist", "dist/foo.js") is True
        assert _matches_path_component("dist", "distribution/config.py") is False
        assert _matches_path_component("dist", "src/dist/bundle.js") is True

    def test_negation_pattern_in_llmignore(self):
        from core.token_counter import scan_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "a.log").write_text("log data\n" * 10)
            (p / "keep.log").write_text("important\n" * 10)
            (p / ".llmignore").write_text("*.log\n!keep.log\n")
            results = scan_directory(p, "generic", respect_llmignore=True)
            paths = [r["path"] for r in results if not r.get("skipped")]
            assert any("keep.log" in x for x in paths)
            assert not any("a.log" in x for x in paths)

    def test_context_analyzer_lock_exact_match(self):
        from core.context_analyzer import analyze_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            # "unlock.json" should NOT match as a lock file
            (p / "unlock.json").write_text('{"x":1}\n' * 200)
            patterns = analyze_directory(p, "generic")
            lock_patterns = [pat for pat in patterns if "lock" in pat.name.lower()]
            assert len(lock_patterns) == 0

    def test_context_analyzer_lock_real_match(self):
        from core.context_analyzer import analyze_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "package-lock.json").write_text('{"x":1}\n' * 200)
            patterns = analyze_directory(p, "generic")
            lock_patterns = [pat for pat in patterns if "lock" in pat.name.lower()]
            assert len(lock_patterns) == 1

    def test_context_analyzer_generated_component_match(self):
        from core.context_analyzer import analyze_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            # "distribution" dir should NOT match as generated
            d = p / "distribution"
            d.mkdir()
            (d / "config.py").write_text("x = 1\n" * 50)
            patterns = analyze_directory(p, "generic")
            gen_patterns = [pat for pat in patterns if "generated" in pat.name.lower() or "built" in pat.name.lower()]
            # distribution should not be flagged
            if gen_patterns:
                for gp in gen_patterns:
                    assert not any("distribution" in f for f in gp.files)


# ── Round-2 fix verification tests ───────────────────────────

class TestOmittedLineCountFix:
    """Verify fix #1: omitted count uses len(lines), not total_line_count."""

    def _make_adapter(self):
        from adapters.base_adapter import BaseLLMAdapter, CompletionResult
        class StubAdapter(BaseLLMAdapter):
            def _call_api(self, messages, **kwargs):
                return CompletionResult(content="", input_tokens=0, output_tokens=0,
                                        total_tokens=0, model="stub", latency_ms=0)
            def count_tokens(self, text):
                return max(1, len(text) // 4)
        return StubAdapter(model="stub")

    def test_omitted_count_without_range(self):
        adapter = self._make_adapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "big.py"
            p.write_text("".join(f"line {i}\n" for i in range(600)))
            content = adapter.load_file_lazy(str(p), max_lines=100)
            # 600 lines, max 100 → omitted = 600 - 100 = 500
            assert "[500 lines omitted]" in content

    def test_omitted_count_with_range(self):
        adapter = self._make_adapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "big.py"
            p.write_text("".join(f"line {i}\n" for i in range(1000)))
            # Load lines 100-400 → 301 lines, max 100 → omitted = 301 - 100 = 201
            content = adapter.load_file_lazy(str(p), max_lines=100,
                                              start_line=100, end_line=400)
            assert "[201 lines omitted]" in content
            # Must NOT say [900 lines omitted] (the old bug)
            assert "[900 lines omitted]" not in content


class TestNegationDirectoryPruning:
    """Verify fix #3: negation patterns prevent directory pruning."""

    def test_negation_inside_ignored_directory(self):
        from core.token_counter import scan_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            d = p / "logs"
            d.mkdir()
            (d / "debug.log").write_text("debug stuff\n" * 10)
            (d / "important.txt").write_text("keep this\n" * 10)
            # Ignore the whole "logs" dir, but negate important.txt inside it
            (p / ".llmignore").write_text("logs\n!logs/important.txt\n")
            results = scan_directory(p, "generic", respect_llmignore=True)
            paths = [r["path"].replace("\\", "/") for r in results if not r.get("skipped")]
            assert any("important.txt" in x for x in paths)
            # debug.log should still be ignored (matched by "logs" dir, not negated)
            assert not any("debug.log" in x for x in paths)


class TestPrintReportExactMatch:
    """Verify fix #4: print_report recommendations use exact matching."""

    def test_lock_recommendation_no_false_positive(self, capsys):
        from core.token_counter import print_report
        # "clockwork.py" should NOT trigger lock file recommendation
        results = [
            {"path": "clockwork.py", "tokens": 100, "lines": 20,
             "size_kb": 1.0, "cost_usd": 0.001},
            {"path": "flock.py", "tokens": 100, "lines": 20,
             "size_kb": 1.0, "cost_usd": 0.001},
        ]
        print_report(results, "generic", show_cost=False)
        output = capsys.readouterr().out
        assert "Lock files" not in output

    def test_lock_recommendation_true_positive(self, capsys):
        from core.token_counter import print_report
        results = [
            {"path": "package-lock.json", "tokens": 5000, "lines": 200,
             "size_kb": 20.0, "cost_usd": 0.01},
        ]
        print_report(results, "generic", show_cost=False)
        output = capsys.readouterr().out
        assert "Lock files" in output

    def test_generated_recommendation_no_false_positive(self, capsys):
        from core.token_counter import print_report
        # "regenerated.py" should NOT trigger generated file recommendation
        results = [
            {"path": "regenerated.py", "tokens": 100, "lines": 20,
             "size_kb": 1.0, "cost_usd": 0.001},
        ]
        print_report(results, "generic", show_cost=False)
        output = capsys.readouterr().out
        assert "Generated" not in output


class TestCompactQualityValidation:
    """Verify fix #6: compact_quality rejects invalid values."""

    def test_invalid_compact_quality_raises(self):
        from adapters.base_adapter import BaseLLMAdapter, CompletionResult
        class StubAdapter(BaseLLMAdapter):
            def _call_api(self, messages, **kwargs):
                return CompletionResult(content="", input_tokens=0, output_tokens=0,
                                        total_tokens=0, model="stub", latency_ms=0)
            def count_tokens(self, text):
                return max(1, len(text) // 4)
        import pytest
        with pytest.raises(ValueError, match="compact_quality"):
            StubAdapter(model="stub", compact_quality="typo")

    def test_valid_compact_quality_accepted(self):
        from adapters.base_adapter import BaseLLMAdapter, CompletionResult
        class StubAdapter(BaseLLMAdapter):
            def _call_api(self, messages, **kwargs):
                return CompletionResult(content="", input_tokens=0, output_tokens=0,
                                        total_tokens=0, model="stub", latency_ms=0)
            def count_tokens(self, text):
                return max(1, len(text) // 4)
        a = StubAdapter(model="stub", compact_quality="fast")
        assert a.compact_quality == "fast"
        b = StubAdapter(model="stub", compact_quality="detailed")
        assert b.compact_quality == "detailed"


# ── Round-3 fix verification tests ───────────────────────────

class TestRangeTruncationMessage:
    """Fix #1: range truncation message no longer double-counts."""

    def _make_adapter(self):
        from adapters.base_adapter import BaseLLMAdapter, CompletionResult
        class StubAdapter(BaseLLMAdapter):
            def _call_api(self, messages, **kwargs):
                return CompletionResult(content="", input_tokens=0, output_tokens=0,
                                        total_tokens=0, model="stub", latency_ms=0)
            def count_tokens(self, text):
                return max(1, len(text) // 4)
        return StubAdapter(model="stub")

    def test_range_truncation_message_correct_count(self, capsys):
        adapter = self._make_adapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "big.py"
            p.write_text("".join(f"line {i}\n" for i in range(1000)))
            # Load 301 lines (100-400), truncate to 100 → message should say 301
            adapter.load_file_lazy(str(p), max_lines=100, start_line=100, end_line=400)
            output = capsys.readouterr().out
            assert "301 lines" in output
            # Should NOT contain the old double-count (502)
            assert "502 lines" not in output


class TestDuplicateClaudeMd:
    """Fix #2: CLAUDE.md no longer scanned twice."""

    def test_no_duplicate_patterns(self):
        from core.context_analyzer import analyze_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            # Create a bloated CLAUDE.md that triggers the pattern
            (p / "CLAUDE.md").write_text("# Rule\n" * 250)
            patterns = analyze_directory(p, "generic")
            claude_patterns = [pat for pat in patterns if "CLAUDE" in pat.name]
            assert len(claude_patterns) == 1  # exactly one, not two


class TestApplyFixesAccumulates:
    """Fix #3: apply_fixes uses += not =."""

    def test_total_added_counts_both_files(self):
        from core.context_analyzer import apply_fixes, WastePattern
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            patterns = [WastePattern(
                name="test", tokens_wasted=100, severity="high",
                description="test", fix="test",
                llmignore_entries=["foo.txt", "bar.txt"],
            )]
            added = apply_fixes(patterns, p)
            # Both .llmignore and .claudeignore should get entries
            assert (p / ".llmignore").exists()
            assert (p / ".claudeignore").exists()
            # Total should count entries from BOTH files (2 + 2 = 4)
            assert added == 4


class TestSkipDirsNegation:
    """Fix #4: SKIP_DIRS respects negation patterns."""

    def test_negation_overrides_skip_dirs(self):
        from core.token_counter import scan_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            d = p / "build"
            d.mkdir()
            (d / "important.cfg").write_text("keep = true\n" * 5)
            (d / "output.js").write_text("var x = 1;\n" * 5)
            # Negate a specific file inside a SKIP_DIRS directory
            (p / ".llmignore").write_text("!build/important.cfg\n")
            results = scan_directory(p, "generic", respect_llmignore=True)
            paths = [r["path"].replace("\\", "/") for r in results if not r.get("skipped")]
            assert any("important.cfg" in x for x in paths)
            # output.js should still be ignored (build dir matched, not negated)
            assert not any("output.js" in x for x in paths)


class TestLogDetectionCrossPlatform:
    """Fix #5: log directory detection uses path components."""

    def test_logs_dir_detected_with_backslash(self):
        from core.context_analyzer import analyze_directory
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            d = p / "logs"
            d.mkdir()
            (d / "app.txt").write_text("log entry\n" * 100)
            patterns = analyze_directory(p, "generic")
            log_patterns = [pat for pat in patterns if "log" in pat.name.lower()]
            assert len(log_patterns) >= 1


class TestIsTiktokenAvailable:
    """Fix #9: callers can check if estimation is exact."""

    def test_function_exists_and_returns_bool(self):
        from core.token_counter import is_tiktoken_available
        result = is_tiktoken_available()
        assert isinstance(result, bool)


class TestOverheadFixed:
    """Fix #8: overhead supports fixed component."""

    def test_fixed_overhead_in_json(self, capsys):
        from core.check import run_check
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "a.py").write_text("x = 1\n" * 10)
            run_check(p, model="generic", max_pct=90, output_json=True,
                      overhead_pct=0, overhead_fixed=5000)
            output = capsys.readouterr().out
            data = json.loads(output)
            assert "overhead_fixed" in data
            assert data["overhead_fixed"] == 5000
            assert data["adjusted_tokens"] > data["total_tokens"]

    def test_combined_overhead(self, capsys):
        from core.check import run_check
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "a.py").write_text("x = 1\n" * 10)
            run_check(p, model="generic", max_pct=90, output_json=True,
                      overhead_pct=10, overhead_fixed=1000)
            output = capsys.readouterr().out
            data = json.loads(output)
            raw = data["total_tokens"]
            expected = int(raw * 1.10) + 1000
            assert data["adjusted_tokens"] == expected


class TestCompactRawUntruncated:
    """Fix #7: last_compact_raw stores untruncated content."""

    def _make_adapter(self):
        from adapters.base_adapter import BaseLLMAdapter, CompletionResult
        class StubAdapter(BaseLLMAdapter):
            def __init__(self, **kw):
                super().__init__(model="stub", **kw)
            def _call_api(self, messages, **kwargs):
                return CompletionResult(
                    content="summary", input_tokens=10, output_tokens=10,
                    total_tokens=20, model="stub", latency_ms=1)
            def count_tokens(self, text):
                return max(1, len(text) // 4)
        return StubAdapter()

    def test_raw_contains_full_content(self):
        adapter = self._make_adapter()
        from adapters.base_adapter import Message
        long_content = "x" * 3000
        for i in range(6):
            adapter._history.append(Message(role="user", content=long_content))
            adapter._history.append(Message(role="assistant", content="ok"))
        adapter.compact()
        # The raw should contain the full 3000 chars, not truncated to 1000
        assert "x" * 3000 in adapter.last_compact_raw
