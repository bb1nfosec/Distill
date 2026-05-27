# Contributing to Distill

Thanks for helping make LLM sessions cheaper for everyone.

## Priority contributions

- `adapters/gemini_adapter.py` - Google Gemini API adapter
- `adapters/litellm_adapter.py` - LiteLLM unified proxy
- `tests/` - unit tests for core tools and adapters
- VS Code extension - real-time token counter in status bar

## Setup

```bash
git clone https://github.com/distill-team/distill
cd distill
pip install -r requirements.txt
python3 core/token_counter.py --path .   # verify it works
```

## Adding a new LLM adapter

1. Create `adapters/your_adapter.py`
2. Extend `BaseLLMAdapter` - implement `count_tokens()` and `_call_api()`
3. Add to `scripts/generate_config.py` detection and config generation
4. Add to `setup.sh` model selection
5. Document in `docs/YOUR_LLM.md`
6. Add example to `scripts/example_usage.py`

```python
from adapters.base_adapter import BaseLLMAdapter, CompletionResult

class YourAdapter(BaseLLMAdapter):
    def count_tokens(self, text: str) -> int:
        # Use your provider's tokenizer
        return len(text) // 4

    def _call_api(self, messages: list[dict], **kwargs) -> CompletionResult:
        response = your_client.complete(messages)
        return CompletionResult(
            content=response.text,
            input_tokens=response.usage.input,
            output_tokens=response.usage.output,
            total_tokens=response.usage.total,
            model=self.model,
            latency_ms=0,
        )
```

## PR checklist

- [ ] `python3 core/token_counter.py --path .` runs without errors
- [ ] `python3 scripts/generate_config.py --output /tmp/test --model all --dry-run` works
- [ ] New adapter includes docstring with a usage example
- [ ] New docs added to `docs/` if the behaviour is non-obvious
