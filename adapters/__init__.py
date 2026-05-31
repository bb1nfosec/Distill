"""skim adapters — universal LLM interface."""
from .base_adapter import BaseLLMAdapter, CompletionResult, SessionStats, Message
from .claude_adapter import ClaudeAdapter
from .openai_adapter import OpenAIAdapter
from .ollama_adapter import OllamaAdapter
from .gemini_adapter import GeminiAdapter

__all__ = [
    "BaseLLMAdapter", "CompletionResult", "SessionStats", "Message",
    "ClaudeAdapter", "OpenAIAdapter", "OllamaAdapter", "GeminiAdapter",
]
__version__ = "0.3.0"
