#!/usr/bin/env python3
"""
example_usage.py - Shows how to use LLM Token Optimizer with each provider.

Run: python3 scripts/example_usage.py --provider claude
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def example_claude():
    """Token-optimized Claude session with auto-compact and subagents."""
    from adapters.claude_adapter import ClaudeAdapter

    claude = ClaudeAdapter(
        model="claude-sonnet-4-5",
        system_prompt=(
            "You are a terse coding assistant. "
            "Respond with code only. No explanations unless asked."
        ),
        enable_caching=True,
        auto_compact_threshold=0.70,  # Compact at 70% context
    )

    # Normal chat
    response = claude.chat("Write a Python function to validate email addresses using regex")
    print("Response:", response[:200], "...\n")

    # Research task in isolated subagent context
    # (won't pollute your main conversation history)
    summary = claude.run_subagent(
        task="What patterns does this codebase use for error handling?",
        context_files=["adapters/base_adapter.py"],
    )
    print("Subagent summary:", summary[:200], "...\n")

    claude.print_stats()


def example_openai():
    """Token-optimized OpenAI session with history trimming."""
    from adapters.openai_adapter import OpenAIAdapter

    gpt = OpenAIAdapter(
        model="gpt-4o-mini",  # Use mini for 15x cost savings on simple tasks
        system_prompt="Senior Python engineer. Code only. No explanations.",
        auto_compact_threshold=0.65,
    )

    response = gpt.chat("Write a FastAPI endpoint that accepts a file upload and returns its line count")
    print("Response:", response[:200], "...\n")
    gpt.print_stats()


def example_ollama():
    """Token-optimized Ollama session with local model."""
    from adapters.ollama_adapter import OllamaAdapter

    llm = OllamaAdapter(
        model="llama3.2",
        num_ctx=8192,      # Always set this - default 2048 is too small
        temperature=0.2,   # Low temp for deterministic code
    )

    print(f"Available models: {llm.list_models()}")

    response = llm.chat("Write a bash function to recursively find all TODO comments in a codebase")
    print("Response:", response[:200], "...\n")
    print(f"Context used: {llm.context_used_pct():.1f}%")
    llm.print_stats()


def example_token_counter():
    """Run the token counter on the current repo."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "core/token_counter.py", "--path", ".", "--model", "claude", "--top", "10"],
        cwd=Path(__file__).parent.parent,
        capture_output=False,
    )


def example_generate_configs():
    """Auto-generate configs for a project."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/generate_config.py",
         "--output", ".", "--model", "all", "--dry-run"],
        cwd=Path(__file__).parent.parent,
        capture_output=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="token-counter",
                        choices=["claude", "openai", "ollama", "token-counter", "generate-configs"])
    args = parser.parse_args()

    examples = {
        "claude":          example_claude,
        "openai":          example_openai,
        "ollama":          example_ollama,
        "token-counter":   example_token_counter,
        "generate-configs": example_generate_configs,
    }

    print(f"\nRunning example: {args.provider}\n{'─'*50}\n")
    try:
        examples[args.provider]()
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install with: pip install -r requirements.txt")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
