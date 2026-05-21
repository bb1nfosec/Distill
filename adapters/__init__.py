"""TokenWise adapters — universal LLM interface."""
from .base_adapter import BaseLLMAdapter, CompletionResult, SessionStats, Message
__all__ = ["BaseLLMAdapter", "CompletionResult", "SessionStats", "Message"]
__version__ = "1.0.0"
