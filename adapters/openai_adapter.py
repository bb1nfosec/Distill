"""
openai_adapter.py — Token-optimized adapter for OpenAI GPT models.

Features:
- Automatic history trimming when approaching context limit
- Lean system prompt patterns
- Structured output to reduce verbose responses
"""

import os
import time
from .base_adapter import BaseLLMAdapter, CompletionResult

try:
    import openai as openai_lib
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI adapter with token optimization.
    
    Usage:
        from adapters.openai_adapter import OpenAIAdapter
        
        gpt = OpenAIAdapter(
            model="gpt-4o",
            system_prompt="Terse coding assistant. Code only, no explanations.",
        )
        response = gpt.chat("Add input validation to the login endpoint")
        gpt.print_stats()
    """

    CONTEXT_LIMITS = {
        "gpt-4.1":          1_047_576,
        "gpt-4.1-mini":     1_047_576,
        "gpt-4.1-nano":     1_047_576,
        "gpt-4o":             128_000,
        "gpt-4o-mini":        128_000,
        "gpt-4-turbo":        128_000,
        "gpt-4":                8_192,
        "gpt-3.5-turbo":      16_385,
        "o3":               200_000,
        "o4-mini":          200_000,
        "o1":               200_000,
        "o1-mini":          128_000,
        "o3-mini":          200_000,
    }

    # Lean system prompt — add your project context below this
    LEAN_SYSTEM_PREFIX = (
        "You are a terse, precise coding assistant. "
        "Rules: respond with code only unless asked; batch all edits; "
        "no preamble; no summaries; never ask to proceed. "
    )

    def __init__(
        self,
        model: str = "gpt-4o",
        system_prompt: str = "",
        max_tokens: int = 4096,
        api_key: str = None,
        base_url: str = None,  # For OpenAI-compatible APIs (LiteLLM, etc.)
        **kwargs
    ):
        context_limit = self.CONTEXT_LIMITS.get(model, 128_000)
        full_system = self.LEAN_SYSTEM_PREFIX + system_prompt if system_prompt else self.LEAN_SYSTEM_PREFIX
        super().__init__(model=model, system_prompt=full_system.strip(),
                         max_tokens=max_tokens, max_context_tokens=context_limit, **kwargs)

        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Run: pip install openai")

        self.client = openai_lib.OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
        )

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model(self.model)
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text) // 4)

    def _call_api(self, messages: list[dict], **kwargs) -> CompletionResult:
        start = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            **kwargs
        )

        latency_ms = int((time.time() - start) * 1000)
        content = response.choices[0].message.content or ""
        usage = response.usage

        return CompletionResult(
            content=content,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            model=self.model,
            latency_ms=latency_ms,
        )

    def trim_history_to_fit(self, target_tokens: int = None):
        """
        Trim oldest messages to fit within target_tokens.
        Preserves the system context and most recent messages.
        """
        target = target_tokens or int(self.max_context_tokens * 0.6)
        
        while self._estimate_context_size() > target and len(self._history) > 2:
            removed = self._history.pop(0)
            removed_tokens = self.count_tokens(removed.content)
            print(f"[TokenOptimizer] Trimmed oldest message: {removed_tokens:,} tokens freed")
