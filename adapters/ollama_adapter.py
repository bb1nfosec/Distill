"""
ollama_adapter.py - Token-optimized adapter for local Ollama models.

Supports: Llama 3, Mistral, Phi, Gemma, CodeLlama, DeepSeek Coder, etc.

Features:
- Explicit context window management (Ollama defaults are tiny)
- Model selection guide by task
- Context size auto-tuning
"""

import os
import time
import json
import urllib.request
import urllib.error
from .base_adapter import BaseLLMAdapter, CompletionResult


class OllamaAdapter(BaseLLMAdapter):
    """
    Ollama adapter for local LLMs with token optimization.
    
    Usage:
        from adapters.ollama_adapter import OllamaAdapter
        
        llm = OllamaAdapter(
            model="llama3.2",
            num_ctx=8192,  # ALWAYS set this - default is 2048 (too small)
        )
        response = llm.chat("Refactor this function to handle null inputs")
        llm.print_stats()
    
    Model recommendations by task:
        Quick edits:      llama3.2:3b    (fast, 4k ctx)
        Feature dev:      llama3.1:8b    (balanced, 8k ctx)
        Code review:      deepseek-coder:6.7b
        Architecture:     llama3.1:70b   (slow, needs GPU)
        Privacy-first:    mistral:7b
    """

    # Recommended context sizes per model
    MODEL_CONTEXTS = {
        "llama3.2":          8_192,
        "llama3.2:3b":       8_192,
        "llama3.1":         32_768,
        "llama3.1:8b":      32_768,
        "llama3.1:70b":     32_768,
        "mistral":          32_768,
        "mistral:7b":       32_768,
        "deepseek-coder":   16_384,
        "deepseek-coder:6.7b": 16_384,
        "phi3":              4_096,
        "gemma2":            8_192,
        "codellama":        16_384,
        "qwen2.5-coder":    32_768,
    }

    def __init__(
        self,
        model: str = "llama3.2",
        system_prompt: str = "",
        max_tokens: int = 2048,
        num_ctx: int = None,  # Context window - ALWAYS set this
        host: str = "http://localhost:11434",
        temperature: float = 0.2,
        **kwargs
    ):
        # Auto-select context size if not specified
        resolved_ctx = num_ctx or self.MODEL_CONTEXTS.get(model.split(":")[0], 8_192)
        
        if num_ctx is None:
            print(f"[OllamaAdapter] num_ctx not set - using {resolved_ctx:,} "
                  f"(Ollama default is 2048, which is too small for most tasks)")

        super().__init__(model=model, system_prompt=system_prompt,
                         max_tokens=max_tokens, max_context_tokens=resolved_ctx, **kwargs)

        self.host = host.rstrip("/")
        self.num_ctx = resolved_ctx
        self.temperature = temperature

        # Verify Ollama is running
        try:
            urllib.request.urlopen(f"{self.host}/api/tags", timeout=3)
        except Exception:
            raise ConnectionError(
                f"Ollama not running at {self.host}. Start it with: ollama serve"
            )

    def count_tokens(self, text: str) -> int:
        # Llama-family: roughly 3.8 chars per token
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            import warnings
            import core.token_counter as _tc
            if not _tc._TIKTOKEN_WARNING_SHOWN:
                warnings.warn(
                    "tiktoken not installed - token counts are approximate "
                    "(character-based estimation). Install tiktoken for accurate counts: "
                    "pip install tiktoken",
                    stacklevel=2,
                )
                _tc._TIKTOKEN_WARNING_SHOWN = True
            return max(1, int(len(text) / 3.8))

    def _call_api(self, messages: list[dict], **kwargs) -> CompletionResult:
        start = time.time()

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": self.num_ctx,
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
        except urllib.error.URLError as e:
            raise ConnectionError(f"Ollama API error: {e}")

        latency_ms = int((time.time() - start) * 1000)
        content = result.get("message", {}).get("content", "")

        # Ollama reports token counts in eval_count / prompt_eval_count
        output_tokens = result.get("eval_count", self.count_tokens(content))
        input_tokens  = result.get("prompt_eval_count", 0)

        return CompletionResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            model=self.model,
            latency_ms=latency_ms,
        )

    def list_models(self) -> list[str]:
        """List locally installed Ollama models."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=5) as resp:
                data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def context_used_pct(self) -> float:
        """How full is the current context?"""
        used = self._estimate_context_size()
        return (used / self.num_ctx) * 100

    @staticmethod
    def generate_modelfile(
        base_model: str = "llama3.2",
        num_ctx: int = 8192,
        temperature: float = 0.2,
        keep_alive: str = "10m",
        system_prompt: str = None,
    ) -> str:
        """Generate an optimized Ollama Modelfile."""
        default_system = (
            "You are a terse, precise coding assistant. "
            "Respond with code only unless explanation is requested. "
            "Batch all edits. No preamble. No summaries. Never ask to proceed."
        )
        system = system_prompt or default_system

        return f"""# Optimized Ollama Modelfile
# Generated by distill
# Usage: ollama create mydev -f Modelfile

FROM {base_model}

# Context window - the most important setting
# Default is 2048 which is too small for real coding tasks
PARAMETER num_ctx {num_ctx}

# Low temperature for deterministic code output
PARAMETER temperature {temperature}

# How long to keep model loaded between requests
PARAMETER keep_alive {keep_alive}

# Reduce verbosity
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.1

SYSTEM \"\"\"{system}\"\"\"
"""
