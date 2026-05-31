"""
base_adapter.py — Abstract base for all LLM adapters.

Every adapter implements the same interface so your optimization
tooling works identically across Claude, OpenAI, Gemini, and Ollama.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class Message:
    role: str         # "system" | "user" | "assistant"
    content: str
    tokens: int = 0


@dataclass
class CompletionResult:
    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    latency_ms: int
    cached_tokens: int = 0


@dataclass
class SessionStats:
    model: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0
    turns: int = 0
    start_time: float = field(default_factory=time.time)
    history: list = field(default_factory=list)

    @property
    def total_tokens(self):
        return self.total_input_tokens + self.total_output_tokens

    @property
    def cache_hit_rate(self):
        if self.total_input_tokens == 0:
            return 0.0
        return self.total_cached_tokens / self.total_input_tokens

    def summary(self) -> dict:
        elapsed = time.time() - self.start_time
        return {
            "model": self.model,
            "turns": self.turns,
            "total_tokens": self.total_tokens,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cached_tokens": self.total_cached_tokens,
            "cache_hit_rate_pct": round(self.cache_hit_rate * 100, 1),
            "elapsed_seconds": round(elapsed, 1),
            "tokens_per_second": round(self.total_tokens / max(elapsed, 1), 1),
        }


class BaseLLMAdapter(ABC):
    """
    Universal interface for any LLM. Extend this to add a new provider.
    
    All adapters support:
    - Token counting before sending
    - Automatic history compaction
    - Session cost tracking
    - Lazy context (only load files when referenced)
    """

    def __init__(
        self,
        model: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        max_context_tokens: int = 100_000,
        auto_compact_threshold: float = 0.75,  # compact at 75% context
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.max_context_tokens = max_context_tokens
        self.auto_compact_threshold = auto_compact_threshold
        self.stats = SessionStats(model=model)
        self._history: list[Message] = []

    # ── Abstract interface ─────────────────────────────────
    
    @abstractmethod
    def _call_api(self, messages: list[dict], **kwargs) -> CompletionResult:
        """Make the actual API call. Implement per provider."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens for this model's tokenizer."""
        ...

    # ── Universal methods (shared by all adapters) ─────────

    def chat(self, user_message: str, **kwargs) -> str:
        """
        Send a message, automatically managing context and compaction.
        Returns the assistant's text response.
        """
        # Check if we should compact before sending
        current_context = self._estimate_context_size()
        if current_context > self.max_context_tokens * self.auto_compact_threshold:
            print(f"[TokenOptimizer] Context at {current_context:,} tokens "
                  f"({current_context/self.max_context_tokens*100:.0f}%) — auto-compacting...")
            self.compact()

        self._history.append(Message(role="user", content=user_message))
        messages = self._build_messages()
        
        result = self._call_api(messages, **kwargs)
        
        self._history.append(Message(role="assistant", content=result.content))
        self.stats.total_input_tokens  += result.input_tokens
        self.stats.total_output_tokens += result.output_tokens
        self.stats.total_cached_tokens += result.cached_tokens
        self.stats.turns += 1

        return result.content

    def compact(self, preserve_last_n: int = 2) -> str:
        """
        Compress conversation history into a summary.
        Preserves the last N turns verbatim for immediate context.
        Returns the summary text.
        """
        if len(self._history) <= preserve_last_n * 2:
            return ""  # Nothing to compact

        to_summarize = self._history[:-preserve_last_n * 2] if preserve_last_n > 0 else self._history
        preserve = self._history[-preserve_last_n * 2:] if preserve_last_n > 0 else []

        history_text = "\n".join(
            f"{m.role.upper()}: {m.content[:500]}{'...' if len(m.content) > 500 else ''}"
            for m in to_summarize
        )

        summary_prompt = (
            f"Summarize this conversation history concisely. "
            f"Preserve: key decisions made, files modified, current task state, any errors encountered.\n\n"
            f"{history_text}"
        )
        
        summary_msg = [{"role": "user", "content": summary_prompt}]
        result = self._call_api(summary_msg)
        
        # Store as a user+assistant pair so the next API call starts with role=user.
        # Anthropic (and OpenAI) require the first message to be role=user.
        summary = f"[Compacted history — earlier conversation summary]\n{result.content}"
        self._history = [
            Message(role="user",      content=summary),
            Message(role="assistant", content="Understood. Continuing from the summary above."),
        ] + preserve
        
        tokens_before = self.count_tokens(history_text)
        tokens_after = self.count_tokens(summary)
        print(f"[TokenOptimizer] Compacted: {tokens_before:,} → {tokens_after:,} tokens "
              f"({(1-tokens_after/max(tokens_before,1))*100:.0f}% reduction)")
        return summary

    def clear(self):
        """Clear all conversation history. Use for completely new tasks."""
        self._history = []
        print("[TokenOptimizer] History cleared.")

    def _estimate_context_size(self) -> int:
        """Estimate total tokens in current context."""
        total = self.count_tokens(self.system_prompt) if self.system_prompt else 0
        for msg in self._history:
            total += self.count_tokens(msg.content) + 4  # 4 for role overhead
        return total

    def _build_messages(self) -> list[dict]:
        """Build messages list for API call."""
        msgs = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        for msg in self._history:
            msgs.append({"role": msg.role, "content": msg.content})
        return msgs

    def print_stats(self):
        """Print session token usage summary."""
        s = self.stats.summary()
        print(f"\n{'─'*50}")
        print(f"  Session stats — {s['model']}")
        print(f"{'─'*50}")
        print(f"  Turns           : {s['turns']}")
        print(f"  Total tokens    : {s['total_tokens']:,}")
        print(f"  Input tokens    : {s['input_tokens']:,}")
        print(f"  Output tokens   : {s['output_tokens']:,}")
        if s['cached_tokens']:
            print(f"  Cached tokens   : {s['cached_tokens']:,} ({s['cache_hit_rate_pct']}% hit rate)")
        print(f"  Elapsed         : {s['elapsed_seconds']}s")
        print(f"{'─'*50}\n")

    def load_file_lazy(self, file_path: str, max_lines: int = 300) -> str:
        """
        Load a file into context only when needed.
        Truncates large files and warns you.
        """
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            return f"[File not found: {file_path}]"
        
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        
        if len(lines) > max_lines:
            original_len = len(lines)
            print(f"[TokenOptimizer] {file_path} has {original_len} lines — "
                  f"truncating to {max_lines}. Use a line range for specific sections.")
            lines = lines[:max_lines]
            lines.append(f"\n... [{original_len - max_lines} more lines truncated]")
        
        content = f"```{path.suffix.lstrip('.')}\n# {file_path}\n{''.join(lines)}```"
        tokens = self.count_tokens(content)
        print(f"[TokenOptimizer] Loaded {file_path}: {tokens:,} tokens")
        return content
