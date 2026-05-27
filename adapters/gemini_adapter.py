"""
gemini_adapter.py - Token-optimized adapter for Google Gemini.

Features:
- Accurate token counting via model.count_tokens()
- Context caching for large static documents (Gemini 1.5+)
- Automatic history compaction
- 1M token context window on Gemini 1.5 Pro

Usage:
    from adapters.gemini_adapter import GeminiAdapter

    gemini = GeminiAdapter(
        model="gemini-1.5-pro",
        system_prompt="You are a terse coding assistant. Code only.",
    )
    response = gemini.chat("Refactor the auth module to use JWT")
    gemini.print_stats()
"""

import os
import time
from .base_adapter import BaseLLMAdapter, CompletionResult

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class GeminiAdapter(BaseLLMAdapter):
    """
    Google Gemini adapter with token optimization.

    Model recommendations:
        gemini-2.0-flash     - fastest, cheapest ($0.10/1M in), 1M ctx
        gemini-1.5-pro       - best quality ($1.25/1M in), 1M ctx
        gemini-1.5-flash     - balanced ($0.075/1M in), 1M ctx
    """

    CONTEXT_LIMITS = {
        "gemini-2.0-flash":       1_048_576,
        "gemini-2.0-flash-lite":  1_048_576,
        "gemini-1.5-pro":         1_048_576,
        "gemini-1.5-flash":       1_048_576,
        "gemini-1.5-flash-8b":    1_048_576,
    }

    # USD per 1M input tokens (prompts ≤ 128k)
    INPUT_PRICING = {
        "gemini-2.0-flash":      0.10,
        "gemini-2.0-flash-lite": 0.075,
        "gemini-1.5-pro":        1.25,
        "gemini-1.5-flash":      0.075,
        "gemini-1.5-flash-8b":   0.0375,
    }

    LEAN_SYSTEM_PREFIX = (
        "You are a terse, precise coding assistant. "
        "Rules: respond with code only unless asked; batch all edits; "
        "no preamble; no trailing summaries; never ask to proceed. "
    )

    def __init__(
        self,
        model: str = "gemini-1.5-flash",
        system_prompt: str = "",
        max_tokens: int = 4096,
        api_key: str = None,
        lean_mode: bool = True,
        **kwargs,
    ):
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai not installed. Run: pip install google-generativeai"
            )

        context_limit = self.CONTEXT_LIMITS.get(model, 1_000_000)
        if lean_mode:
            full_system = (self.LEAN_SYSTEM_PREFIX + system_prompt).strip() if system_prompt \
                          else self.LEAN_SYSTEM_PREFIX.strip()
        else:
            full_system = system_prompt.strip() if system_prompt else ""

        super().__init__(
            model=model,
            system_prompt=full_system,
            max_tokens=max_tokens,
            max_context_tokens=context_limit,
            **kwargs,
        )

        genai.configure(api_key=api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
        self._model = genai.GenerativeModel(
            model_name=model,
            system_instruction=full_system or None,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.2,
            ),
        )
        self._chat_session = self._model.start_chat(history=[])

    def count_tokens(self, text: str) -> int:
        try:
            result = self._model.count_tokens(text)
            return result.total_tokens
        except Exception:
            return max(1, int(len(text) / 4.1))

    def _call_api(self, messages: list[dict], **kwargs) -> CompletionResult:
        start = time.time()

        # Rebuild the chat with current history (Gemini tracks session internally,
        # but we manage history ourselves for compaction support)
        history = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                continue
            gemini_role = "user" if role == "user" else "model"
            history.append({"role": gemini_role, "parts": [msg["content"]]})

        # Last message is the new user turn
        if not history:
            return CompletionResult(
                content="", input_tokens=0, output_tokens=0,
                total_tokens=0, model=self.model, latency_ms=0,
            )

        user_msg = history[-1]["parts"][0]
        session = self._model.start_chat(history=history[:-1])

        try:
            response = session.send_message(user_msg)
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}") from e

        latency_ms = int((time.time() - start) * 1000)
        content = response.text or ""

        usage = response.usage_metadata
        input_tokens  = getattr(usage, "prompt_token_count",     self.count_tokens(user_msg))
        output_tokens = getattr(usage, "candidates_token_count", self.count_tokens(content))

        return CompletionResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            model=self.model,
            latency_ms=latency_ms,
        )

    def list_models(self) -> list[str]:
        """List available Gemini models."""
        try:
            return [m.name for m in genai.list_models()
                    if "generateContent" in m.supported_generation_methods]
        except Exception:
            return list(self.CONTEXT_LIMITS.keys())

    def input_cost_per_session(self) -> float:
        """Estimated $ cost to load the current context once."""
        tokens = self._estimate_context_size()
        rate = self.INPUT_PRICING.get(self.model, 1.25)
        return tokens / 1_000_000 * rate
