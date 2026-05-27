# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Contact the project maintainers with the subject line `[SECURITY] distill — <short description>`.

Include:
- A description of the vulnerability and its impact
- Steps to reproduce
- Affected versions
- Any suggested fix, if you have one

You will receive an acknowledgement within 48 hours and a resolution timeline within 7 days.

## Scope

The main surface area to consider:

- **API key handling** — adapters read keys from environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). They are never logged or written to disk.
- **File path inputs** — `token_counter.py` and `context_analyzer.py` accept `--path` arguments. Paths are resolved with `Path.resolve()` and only read, never executed.
- **Dependencies** — `tiktoken`, `anthropic`, `openai`. Pin versions in production environments.
