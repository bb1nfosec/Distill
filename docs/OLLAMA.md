# Ollama — Local LLM Token Optimization Guide

## The most important setting: `num_ctx`

Ollama's default context window is **2,048 tokens**. This is far too small for real coding tasks. Always set it.

```bash
# In your Modelfile:
PARAMETER num_ctx 8192    # Good for most tasks
PARAMETER num_ctx 16384   # Large files or complex sessions
PARAMETER num_ctx 32768   # Extended sessions (needs more RAM)
```

## Model selection by task

| Task | Best model | `num_ctx` | RAM needed |
|---|---|---|---|
| Quick edits, simple questions | `llama3.2:3b` | 4k | ~3GB |
| Feature development | `llama3.1:8b` | 8k | ~6GB |
| Code review, analysis | `deepseek-coder:6.7b` | 8k | ~5GB |
| Architecture discussions | `llama3.1:70b` | 16k | ~48GB |
| Privacy-sensitive work | `mistral:7b` | 8k | ~5GB |
| Fast iteration | `phi3:mini` | 4k | ~2GB |

## Generate an optimized Modelfile

```bash
python3 scripts/generate_config.py --output . --model ollama
# Creates .llm/Modelfile

# Apply it:
ollama create mydev -f .llm/Modelfile
ollama run mydev
```

Or generate programmatically:

```python
from adapters.ollama_adapter import OllamaAdapter

modelfile = OllamaAdapter.generate_modelfile(
    base_model="llama3.1:8b",
    num_ctx=16384,
    temperature=0.2,
    keep_alive="10m",
)
print(modelfile)
```

## Using the OllamaAdapter

```python
from adapters.ollama_adapter import OllamaAdapter

llm = OllamaAdapter(
    model="llama3.2",
    num_ctx=8192,       # Always set this!
    temperature=0.2,    # Low for deterministic code output
)

# Check available models
print(llm.list_models())

response = llm.chat("Add error handling to this function")
print(f"Context used: {llm.context_used_pct():.1f}%")
llm.print_stats()
```

## Context window vs RAM tradeoff

Each token in the context window costs ~0.5–1MB of VRAM:

```
Model          num_ctx    VRAM needed
─────────────  ────────   ──────────
llama3.2:3b    4096       ~3.5GB
llama3.1:8b    8192       ~8GB
llama3.1:8b    16384      ~10GB
llama3.1:8b    32768      ~14GB
llama3.1:70b   16384      ~50GB
```

For CPU-only inference, 8k context is a good limit before things get slow.

## `keep_alive` — control RAM usage

```bash
PARAMETER keep_alive 10m   # Keep model loaded for 10 minutes after last use
PARAMETER keep_alive 0     # Unload immediately after each request (saves RAM)
PARAMETER keep_alive -1    # Keep loaded forever
```

## Ollama doesn't have /compact — do it manually

Ollama models have no built-in session compaction. Use the adapter:

```python
llm = OllamaAdapter(model="llama3.1:8b", num_ctx=16384)

# Work on task...
response = llm.chat("Implement the user auth flow")

# After finishing, compact manually
llm.compact()

# Or clear entirely for a new task
llm.clear()
```

## Running multiple models efficiently

```bash
# Pull models once
ollama pull llama3.2:3b
ollama pull llama3.1:8b
ollama pull deepseek-coder:6.7b

# Quick edits → small fast model
ollama run llama3.2:3b "Fix the typo in src/api/routes.ts"

# Complex feature → bigger model
ollama run llama3.1:8b "Design the authentication architecture"

# Code-specific task → specialized model
ollama run deepseek-coder:6.7b "Review this PR for security issues"
```
