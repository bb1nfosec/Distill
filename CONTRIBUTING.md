# Contributing to skim

Thanks for helping make LLM token usage cheaper and more visible for everyone.

## What to work on

Priority contributions:

| Area | What's needed |
|------|--------------|
| `tests/` | Unit + integration tests (coverage is low) |
| `adapters/litellm_adapter.py` | LiteLLM unified proxy support |
| VS Code extension | Real-time token counter in the status bar |
| `server/` | PostgreSQL backend for larger deployments |
| `docs/` | Examples, tutorials, integration guides |

## Setup

```bash
git clone https://github.com/bb1nfosec/skim
cd skim

# Install all optional deps for development
pip install -e '.[all,dev]'

# Verify the core works
python3 -m core.cli scan --path .
python3 -m core.cli proxy --port 7474 --no-browser &
sleep 2 && curl http://localhost:7474/health
```

## Adding a new LLM adapter

1. Create `adapters/your_adapter.py` — extend `BaseLLMAdapter`
2. Implement `count_tokens(text: str) -> int` and `_call_api(messages, **kwargs) -> CompletionResult`
3. Add to `adapters/__init__.py`
4. Add context limits to `core/token_counter.py:CONTEXT_LIMITS`
5. Document in `docs/YOUR_LLM.md`
6. Add example to `scripts/example_usage.py`

```python
from adapters.base_adapter import BaseLLMAdapter, CompletionResult

class YourAdapter(BaseLLMAdapter):
    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)   # replace with real tokenizer

    def _call_api(self, messages: list[dict], **kwargs) -> CompletionResult:
        # call your LLM API
        ...
```

## Code standards

- **Python 3.10+** — use `str | None` union syntax, not `Optional[str]`
- **No new hard dependencies** in `core/` — it must work with stdlib only
- Optional deps go in `pyproject.toml [project.optional-dependencies]`
- Type hints on all new public functions
- No docstrings needed unless the function has non-obvious semantics
- Tests go in `tests/` and follow the `test_*.py` naming convention

## Running tests

```bash
python3 -m pytest tests/ -v
```

## Submitting a PR

1. Fork the repo and create a branch: `git checkout -b feat/your-feature`
2. Make your changes
3. Run tests: `python3 -m pytest tests/ -v`
4. Run syntax check: `python3 -m py_compile core/*.py server/*.py adapters/*.py`
5. Submit a PR — fill out the template

## Project structure

```
core/           Proxy, scanner, secrets, hooks, baseline, config, audit
adapters/       LLM adapters (Claude, OpenAI, Gemini, Ollama)
server/         Flask dashboard, auth, DB, webhooks
server/static/  Dashboard HTML (local + enterprise)
skim_mcp/       MCP server (Claude Desktop integration)
docs/           Documentation
tests/          Test suite
scripts/        Config generators, examples
```

## Reporting bugs

Use [GitHub Issues](https://github.com/bb1nfosec/skim/issues). For security vulnerabilities, see [SECURITY.md](SECURITY.md).
