<div align="center">

# distill

**You're probably sending `.env` files to your LLM right now. And paying for it.**

[![PyPI](https://img.shields.io/pypi/v/distill-llm?color=0073b7&logo=pypi&logoColor=white)](https://pypi.org/project/distill-llm/)
[![CI](https://github.com/bb1nfosec/Distill/actions/workflows/ci.yml/badge.svg)](https://github.com/bb1nfosec/Distill/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![Zero hard deps](https://img.shields.io/badge/core-zero%20hard%20deps-f59e0b)](pyproject.toml)

[Install](#install) · [CLI](#cli) · [MCP Server](#mcp-server) · [Python API](#python-api) · [Benchmarks](#benchmarks) · [Try Online](https://bb1nfosec.github.io/Distill)

![distill demo](assets/demo.gif)

</div>

---

Distill scans your codebase, tells you exactly what's eating your tokens and what it costs, then writes the ignore rules for you.

```
$ distill fix --path ./my-project

  distill fix  —  ./my-project
  ──────────────────────────────────────────────────────
  Before  : 166.8k tokens  (83.4% ctx)  $0.50/session

  Pattern                    Severity    Tokens saved  Rules added
  ──────────────────────────────────────────────────────────────────
  Lock files                 HIGH           160.3k     + 7 rules
  Test snapshots             HIGH             4.1k     + 2 rules

  ✓ Written to .llmignore

  After   : 6.5k tokens  (3.2% ctx)  $0.02/session
  Saved   : 160.3k tokens  (96.1% reduction)  $0.48/session
  Now     : 51 sessions / $1
```

---

## Why this costs more than you think

Every LLM re-reads your full conversation history on every turn. That means cost grows quadratically, not linearly.

```
Turn  1:   500 (system) +       0 (history) + 200 (msg) =     700 tokens
Turn  5:   500          +   4,000            + 200       =   4,700 tokens
Turn 10:   500          +  18,000            + 200       =  18,700 tokens   ← 26× turn 1
Turn 20:   500          +  76,000            + 200       =  76,700 tokens   ← 109× turn 1
```

A typical Claude Code session runs 15–20 turns. At Sonnet pricing, a bloated codebase loads costs **$0.23/session** before you type a single character. Multiply by your team.

`package-lock.json` alone is 15,000–120,000 tokens. Every. Single. Session. It's the first thing `distill fix` removes.

---

## Install

```bash
pip install "distill-llm[tiktoken]"   # recommended — exact token counts
pip install "distill-llm[all]"        # + Claude, OpenAI, Gemini adapters + MCP server
pip install distill-llm               # core only, zero hard dependencies
```

---

## CLI

```bash
distill scan     --path .                     # see what's burning tokens + dollar cost
distill analyze  --path .                     # find the waste patterns
distill fix      --path .                     # write .llmignore rules automatically
distill check    --path . --max-pct 30        # CI gate — exits 1 if over budget
distill generate --output . --model all       # generate CLAUDE.md, Modelfile, configs
```

### scan

Shows every file that would enter your LLM context and its exact token cost.

```bash
$ distill scan --path ./my-project

  distill — Context Audit
  ──────────────────────────────────────────────────────────────
  Model         : claude  ($3.00 / 1M input tokens)
  Files scanned : 247
  Total tokens  : 182.4k  (91.2% of context)
  Per-session $ : $0.5472
  Sessions / $1 : 1

  File                                        Tokens      Cost
  ──────────────────────────────────────────  ──────  ──────────
  package-lock.json                           122.0k    $0.3660
  tsconfig.tsbuildinfo                        103.2k    $0.3096
  src/generated/schema.ts                       4.1k    $0.0123
  src/auth/middleware.ts                        1.8k    $0.0054
```

### fix

Detects waste patterns, writes the rules, shows before/after.

```bash
distill fix --path .                     # auto-fix HIGH severity patterns
distill fix --path . --dry-run           # preview savings without writing
distill fix --path . --min-severity low  # catch medium/low patterns too
distill fix --path . --model gpt-4o      # price against GPT-4o instead
```

### check — CI gate

```bash
distill check --path . --max-pct 30
distill check --path . --max-pct 30 --fail-on-waste   # also fail on un-ignored lock files
distill check --path . --json                          # machine-readable
```

```yaml
# .github/workflows/ci.yml
- name: Token budget gate
  run: distill check --path . --max-pct 30 --fail-on-waste
```

### analyze

Deeper report: severity, root cause, and the exact `.llmignore` entry that fixes it.

```bash
distill analyze --path .          # full report
distill analyze --path . --fix    # report + apply fixes
distill analyze --path . --json   # pipe to your own tooling
```

---

## MCP Server

Makes distill a native tool Claude can call on its own — no slash commands, no manual prompting.

```bash
pip install "distill-llm[mcp]"
```

Add to `claude_desktop_config.json` or `.mcp.json`:

```json
{
  "mcpServers": {
    "distill": { "command": "distill-mcp" }
  }
}
```

Claude gets five tools: `scan_tokens`, `analyze_context`, `fix_context`, `check_budget`, `generate_llmignore`. It'll call them when relevant without you asking.

**Claude Code slash commands** — drop `.claude/commands/` into any project:

```
/distill-scan     token audit with dollar costs
/distill-analyze  waste pattern detection
/distill-fix      auto-fix with before/after
/distill-check    CI budget gate
/distill-generate generate .llmignore
```

→ [Full org deployment guide](docs/mcp-setup.md)

---

## Python API

Same interface across all providers. Swap LLMs by changing one line.

```python
from adapters import ClaudeAdapter, OpenAIAdapter, GeminiAdapter, OllamaAdapter

llm = ClaudeAdapter(model="claude-sonnet-4-5", enable_caching=True)
# llm = OpenAIAdapter(model="gpt-4o")
# llm = GeminiAdapter(model="gemini-2.0-flash")   # $0.10/1M, 1M ctx window
# llm = OllamaAdapter(model="llama3.2", num_ctx=8192)

response = llm.chat("Refactor the auth module to use JWT")
llm.compact()       # compress history — call between task phases
llm.print_stats()   # tokens used, cache hit rate, latency
```

**Prompt caching (Claude)** — static context is cached automatically. Cache hit = 90% cheaper than a fresh read.

**Subagents** — run research in a separate context window so it doesn't pile up in yours:

```python
summary = claude.run_subagent(
    task="How does our auth handle token refresh? Any edge cases?",
    context_files=["src/auth/jwt.ts", "src/middleware/authGuard.ts"]
)
# [Subagent] Research complete — 4,200 tokens used in separate context

response = claude.chat(f"Given: {summary}\nNow add refresh token rotation.")
```

**Lazy file loading** — warns on oversized files, truncates at a line limit:

```python
content = llm.load_file_lazy("src/api/routes.ts", max_lines=150)
# [distill] Loaded src/api/routes.ts: 820 tokens

response = llm.chat(f"Add rate limiting:\n{content}")
```

**Add any LLM in ~30 lines:**

```python
from adapters.base_adapter import BaseLLMAdapter, CompletionResult

class MyLLMAdapter(BaseLLMAdapter):
    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def _call_api(self, messages: list[dict], **kwargs) -> CompletionResult:
        response = my_client.complete(messages)
        return CompletionResult(
            content=response.text,
            input_tokens=response.usage.input,
            output_tokens=response.usage.output,
            total_tokens=response.usage.total,
            model=self.model,
            latency_ms=response.latency_ms,
        )

# Gets auto-compact, history management, stats, lazy loading for free
llm = MyLLMAdapter(model="my-model-v1", auto_compact_threshold=0.70)
```

---

## Benchmarks

Real numbers on real projects.

### Token estimation accuracy

| Sample | Size | Error vs ground truth | Time |
|---|---:|---:|---:|
| Inline comment | 41 chars | **0.00%** | 8.5 ms |
| Full adapter (~8 KB) | 7,768 chars | **0.00%** | 1.1 ms |
| Lock file slice (50 KB) | 50,000 chars | **0.00%** | 9.7 ms |
| Large Python file (~35 KB) | 35,000 chars | **0.00%** | 5.0 ms |

### Scan throughput

| Project | Files | Tokens | Time | Throughput |
|---|---:|---:|---:|---:|
| distill (this repo) | 26 | 33,374 | 21 ms | 1.62 M tok/s |
| TradingAgents (Python) | 85 | 85,412 | 51 ms | 1.66 M tok/s |
| vaathi-main (Next.js) | 520 | 1,876,732 | 1,028 ms | 1.83 M tok/s |

### `distill fix` on a real Next.js project

| | Tokens | Context % |
|---|---:|---:|
| Before | 166,800 | 83.4% |
| After | 6,500 | 3.2% |
| **Saved** | **160,300** | **96.1% reduction** |

`package-lock.json` (122k tokens), `tsconfig.tsbuildinfo` (103k), test snapshots (4k) — all gone in one command.

### Compaction savings over a 10-turn session

| | Input tokens |
|---|---:|
| Without compaction | 37,760 |
| With compaction at turn 4 | 21,572 |
| **Saved** | **16,188 (42.9%)** |

```bash
python3 benchmarks/run_benchmarks.py                  # run on this repo
python3 benchmarks/run_benchmarks.py --path /yours    # run on your project
```

---

## Five habits that cut costs more than any tool

**Batch prompts.** Five sequential turns generate 5× the history. One batched turn generates none.
```
❌  "Add validation to login"        ✅  "In one pass:
    "Now add it to register"              1. Validation on login + register + reset
    "And password reset too"              2. Standardize error messages
    "Update error messages"               3. Update affected tests"
    "Fix the tests"
```

**`.llmignore` first.** Run `distill fix` once on any project before you start. It takes 10 seconds and saves the most money.

**Keep `CLAUDE.md` lean.** It loads on every single session — every line is a per-session tax forever.
```
CLAUDE.md size       Cost/session    Cost over 100 sessions
───────────────────  ──────────────  ──────────────────────
 50 lines (~250t)       $0.00075           $0.075
200 lines (~1kt)        $0.003             $0.30
500 lines (~2.5kt)      $0.0075            $0.75
```

**Research in a subagent.** Files you load for research stay in context for the rest of the session. Push them to a subagent and only the summary comes back.

**Compact between tasks.** History never gets cheaper. `/compact` in Claude Code or `llm.compact()` when switching tasks — 42.9% token reduction in a 10-turn session.

---

## Supported providers

| Provider | Adapter | Config generated | Notes |
|---|---|---|---|
| Claude API | `ClaudeAdapter` | system prompt | Prompt caching — up to 90% cost cut on static context |
| Claude Code | — | `CLAUDE.md` + `.claudeignore` | Subagents, `/compact`, lean config |
| GPT-4o / mini | `OpenAIAdapter` | `openai_system.md` | Works with any OpenAI-compatible endpoint |
| Gemini 2.0 Flash | `GeminiAdapter` | `gemini_system.md` | 1M ctx window, $0.10/1M |
| Ollama (local) | `OllamaAdapter` | `Modelfile` | `num_ctx` tuning, free |
| LiteLLM / Groq | `OpenAIAdapter(base_url=...)` | OpenAI-compat | Any proxy |

---

## Security note

`.llmignore` blocks `.env`, `.env.*`, `*.pem`, `*.key`, and credential files by default. `distill check --fail-on-waste` in CI catches un-ignored secrets and lock files before they hit a PR. The file itself is checked in and diff-able — treat it like any other security config.

---

## Contributing

PRs welcome. [CONTRIBUTING.md](CONTRIBUTING.md) has the setup.

Most useful right now:
- `adapters/litellm_adapter.py` — LiteLLM unified proxy support
- VS Code extension — real-time token counter in the status bar
- Smarter oversized-file handling in `distill fix`
- More test coverage

---

## License

MIT — [LICENSE](LICENSE)

---

<div align="center">

Built after one too many `Claude usage limit reached` messages at 2am.

**If it saved you tokens, drop a ⭐**

</div>
