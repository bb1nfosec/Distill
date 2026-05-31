"""
claude_adapter.py — Token-optimized adapter for Anthropic Claude.

Features:
- Prompt caching (up to 90% cost reduction on repeated context)
- Automatic /compact equivalent
- Claude Code CLAUDE.md generator
- Subagent pattern for research isolation
"""

import os
import json
from .base_adapter import BaseLLMAdapter, CompletionResult, Message

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class ClaudeAdapter(BaseLLMAdapter):
    """
    Claude adapter with prompt caching and token optimization.
    
    Usage:
        from adapters.claude_adapter import ClaudeAdapter
        
        claude = ClaudeAdapter(
            model="claude-sonnet-4-5",
            system_prompt="You are a terse coding assistant. No explanations unless asked.",
            enable_caching=True,
        )
        
        response = claude.chat("Refactor the auth module to use JWT")
        claude.print_stats()
    """

    # Context window limits per Claude model
    CONTEXT_LIMITS = {
        "claude-opus-4-8":              200_000,
        "claude-opus-4-5":              200_000,
        "claude-sonnet-4-6":            200_000,
        "claude-sonnet-4-5":            200_000,
        "claude-haiku-4-5-20251001":    200_000,
        "claude-haiku-4-5":             200_000,
        "claude-3-7-sonnet-20250219":   200_000,
        "claude-3-5-sonnet-20241022":   200_000,
        "claude-3-5-haiku-20241022":    200_000,
        "claude-3-opus-20240229":       200_000,
    }

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        system_prompt: str = "",
        max_tokens: int = 4096,
        enable_caching: bool = True,
        api_key: str = None,
        **kwargs
    ):
        context_limit = self.CONTEXT_LIMITS.get(model, 200_000)
        super().__init__(model=model, system_prompt=system_prompt,
                         max_tokens=max_tokens, max_context_tokens=context_limit, **kwargs)
        
        self.enable_caching = enable_caching
        
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            return max(1, len(text) // 4)

    def _call_api(self, messages: list[dict], **kwargs) -> CompletionResult:
        import time
        start = time.time()
        
        # Build system with caching if enabled
        system = []
        if self.system_prompt:
            system_block = {"type": "text", "text": self.system_prompt}
            if self.enable_caching:
                system_block["cache_control"] = {"type": "ephemeral"}
            system.append(system_block)

        # Apply caching to large static context (like file contents)
        api_messages = []
        for i, msg in enumerate(messages):
            if msg["role"] == "system":
                continue  # handled above
            m = {"role": msg["role"], "content": msg["content"]}
            # Cache the last assistant message (often contains large file content)
            if self.enable_caching and msg["role"] == "assistant" and i < len(messages) - 2:
                if isinstance(msg["content"], str) and len(msg["content"]) > 1000:
                    m["content"] = [{"type": "text", "text": msg["content"],
                                     "cache_control": {"type": "ephemeral"}}]
            api_messages.append(m)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system if system else anthropic.NOT_GIVEN,
            messages=api_messages,
            **kwargs
        )

        latency_ms = int((time.time() - start) * 1000)
        content = response.content[0].text if response.content else ""
        
        usage = response.usage
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0
        
        return CompletionResult(
            content=content,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + usage.output_tokens,
            model=self.model,
            latency_ms=latency_ms,
            cached_tokens=cached,
        )

    def run_subagent(self, task: str, context_files: list[str] = None) -> str:
        """
        Run a research task in a separate context window (subagent pattern).
        Returns only a summary — keeps your main conversation clean.
        
        Example:
            summary = claude.run_subagent(
                "Investigate how authentication handles token refresh",
                context_files=["src/auth/", "src/middleware/auth.ts"]
            )
        """
        subagent_system = (
            "You are a code research assistant. Analyze the provided code and return a "
            "concise, structured summary. Maximum 500 tokens. Focus on: key patterns, "
            "data flow, potential issues, and what the calling agent needs to know."
        )

        content_parts = [f"Research task: {task}\n"]
        if context_files:
            for fp in context_files:
                content = self.load_file_lazy(fp, max_lines=200)
                content_parts.append(content)

        # Fresh subagent — no history; forward api_key so explicit keys aren't lost
        sub = ClaudeAdapter(
            model="claude-haiku-4-5-20251001",
            system_prompt=subagent_system,
            max_tokens=1024,
            enable_caching=False,
            api_key=self.client.api_key,
        )
        result = sub.chat("\n".join(content_parts))
        
        tokens_used = sub.stats.total_tokens
        print(f"[Subagent] Research complete — {tokens_used:,} tokens used in separate context")
        return result

    @staticmethod
    def generate_claude_md(
        project_type: str = "node",
        pkg_manager: str = "pnpm",
        test_cmd: str = "pnpm test",
        lint_cmd: str = "pnpm typecheck",
        forbidden_dirs: list[str] = None,
        custom_notes: str = "",
        max_lines: int = 80,
    ) -> str:
        """Generate a lean CLAUDE.md for your project."""
        forbidden = forbidden_dirs or ["node_modules", "dist", "build", ".git", "coverage"]
        
        lines = [
            "# Project",
            f"- Type: {project_type}",
            f"- Package manager: {pkg_manager}",
            f"- Test: `{test_cmd}`",
            f"- Lint: `{lint_cmd}`",
            "",
            "# Response rules",
            "- Batch all related edits into one pass. Never make partial changes and ask to continue.",
            "- No explanatory prose unless asked. Code + inline comments only.",
            "- Never ask 'shall I proceed?' — just execute.",
            "- Read only files directly relevant to the task.",
            "- Keep responses terse. No summaries of what you just did.",
            "",
            "# Forbidden paths — never read these",
        ]
        for d in forbidden:
            lines.append(f"- {d}/")
        
        lines.append("")
        lines.append("# Research")
        lines.append("- For codebase exploration, delegate to a subagent. Return only the summary.")
        lines.append("")
        lines.append("# Session")
        lines.append("- Run /compact after completing each feature or work phase.")
        lines.append("- Use /btw for quick lookups — keeps them out of history.")

        if custom_notes:
            lines.append("")
            lines.append("# Notes")
            lines.extend(custom_notes.strip().split("\n"))

        result = "\n".join(lines)
        
        # Warn if over limit
        if len(lines) > max_lines:
            print(f"[Warning] CLAUDE.md is {len(lines)} lines — target under {max_lines}")
        
        return result
