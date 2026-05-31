## What does this PR do?

<!-- One sentence summary -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] New LLM adapter
- [ ] Enterprise / server
- [ ] Refactor
- [ ] Documentation
- [ ] Tests

## Checklist

- [ ] `python3 -m pytest tests/ -v` passes
- [ ] `python3 -m py_compile core/*.py server/*.py adapters/*.py` clean
- [ ] `python3 -m core.cli scan --path .` runs without errors
- [ ] New adapter (if any) extends `BaseLLMAdapter` and has a docstring example
- [ ] No new hard dependencies added to `core/` (must remain stdlib-only)
- [ ] Docs updated if behaviour or API changed
- [ ] CHANGELOG.md entry added

## Notes for reviewers

<!-- Anything non-obvious, trade-offs made, follow-up work needed -->
