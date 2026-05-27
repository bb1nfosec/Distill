"""
base_adapter.py - Abstract base for all LLM adapters.

Every adapter implements the same interface so your optimization
tooling works identically across Claude, OpenAI, Gemini, and Ollama.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
        compact_quality: str = "detailed",  # "fast" | "detailed"
    ):
        if compact_quality not in ("fast", "detailed"):
            raise ValueError(f"compact_quality must be 'fast' or 'detailed', got {compact_quality!r}")
        self.model = model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.max_context_tokens = max_context_tokens
        self.auto_compact_threshold = auto_compact_threshold
        self.compact_quality = compact_quality
        self.stats = SessionStats(model=model)
        self._history: list[Message] = []
        self._last_compact_raw: str = ""

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
                  f"({current_context/self.max_context_tokens*100:.0f}%) - auto-compacting...")
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

    @property
    def last_compact_raw(self) -> str:
        """The raw (pre-summary) history text from the last compaction, for inspection."""
        return self._last_compact_raw

    def compact(self, preserve_last_n: int = 2) -> str:
        """
        Compress conversation history into a summary.
        Preserves the last N turns verbatim for immediate context.
        Returns the summary text.

        When ``compact_quality`` is ``"detailed"``, uses a structured JSON prompt
        that extracts decisions, files_modified, errors, current_state, and
        open_questions.  Truncation limit is raised to 1000 chars per message.
        """
        if len(self._history) <= preserve_last_n * 2:
            return ""  # Nothing to compact

        to_summarize = self._history[:-preserve_last_n * 2] if preserve_last_n > 0 else self._history
        preserve = self._history[-preserve_last_n * 2:] if preserve_last_n > 0 else []

        trunc = 1000 if self.compact_quality == "detailed" else 500
        history_text = "\n".join(
            f"{m.role.upper()}: {m.content[:trunc]}{'...' if len(m.content) > trunc else ''}"
            for m in to_summarize
        )
        # Store untruncated version for inspection
        self._last_compact_raw = "\n".join(
            f"{m.role.upper()}: {m.content}" for m in to_summarize
        )

        if self.compact_quality == "detailed":
            summary_prompt = (
                "Summarize this conversation history as structured JSON with the keys: "
                "decisions (list of key decisions made), files_modified (list of file paths changed), "
                "errors (list of errors encountered), current_state (string describing where things stand), "
                "open_questions (list of unresolved items). Be concise but preserve important detail.\n\n"
                f"{history_text}"
            )
        else:
            summary_prompt = (
                "Summarize this conversation history concisely. "
                "Preserve: key decisions made, files modified, current task state, any errors encountered.\n\n"
                f"{history_text}"
            )

        summary_msg = [{"role": "user", "content": summary_prompt}]
        result = self._call_api(summary_msg)

        summary = f"[Compacted history]\n{result.content}"
        self._history = [Message(role="assistant", content=summary)] + preserve

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
        print(f"  Session stats - {s['model']}")
        print(f"{'─'*50}")
        print(f"  Turns           : {s['turns']}")
        print(f"  Total tokens    : {s['total_tokens']:,}")
        print(f"  Input tokens    : {s['input_tokens']:,}")
        print(f"  Output tokens   : {s['output_tokens']:,}")
        if s['cached_tokens']:
            print(f"  Cached tokens   : {s['cached_tokens']:,} ({s['cache_hit_rate_pct']}% hit rate)")
        print(f"  Elapsed         : {s['elapsed_seconds']}s")
        print(f"{'─'*50}\n")

    def load_file_lazy(
        self,
        file_path: str,
        max_lines: int = 300,
        start_line: int = None,
        end_line: int = None,
    ) -> str:
        """
        Load a file into context only when needed.
        Truncates large files showing first half + last half with an omission marker.

        Parameters:
            start_line: 1-based start line for range-based loading.
            end_line:   1-based end line (inclusive) for range-based loading.
        """
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            return f"[File not found: {file_path}]"

        with open(path, encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()

        total_line_count = len(all_lines)

        # Range-based loading
        if start_line is not None or end_line is not None:
            s = max((start_line or 1) - 1, 0)
            e = min(end_line or total_line_count, total_line_count)
            lines = all_lines[s:e]
            range_label = f" (lines {s+1}-{e} of {total_line_count})"
        else:
            lines = all_lines
            range_label = ""

        if len(lines) > max_lines:
            omitted = len(lines) - max_lines
            half = max_lines // 2
            head = lines[:half]
            tail = lines[-half:]
            if start_line is not None or end_line is not None:
                print(f"[TokenOptimizer] {file_path} range has {len(lines)} lines - "
                      f"truncating to {max_lines}. Narrow the range for full content.")
            else:
                print(f"[TokenOptimizer] {file_path} has {total_line_count} lines - "
                      f"truncating to {max_lines}. Use start_line/end_line for specific sections.")
            lines = head + [f"\n... [{omitted} lines omitted]\n"] + tail

        content = f"```{path.suffix.lstrip('.')}\n# {file_path}{range_label}\n{''.join(lines)}```"
        tokens = self.count_tokens(content)
        print(f"[TokenOptimizer] Loaded {file_path}: {tokens:,} tokens")
        return content
