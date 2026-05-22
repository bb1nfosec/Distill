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

Distill scans your codebase, shows you exactly which files eat your Claude/GPT tokens and what they cost, then **fixes it automatically**.

One command. Before/after diff. Works on any LLM.

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

## The math that makes this matter

Every LLM re-reads your entire conversation history on every turn. That means token cost is **quadratic**, not linear.

```
Turn  1:   500 (system) +       0 (history) + 200 (msg) =     700 tokens
Turn  5:   500          +   4,000            + 200       =   4,700 tokens
Turn 10:   500          +  18,000            + 200       =  18,700 tokens   ← 26× turn 1
Turn 20:   500          +  76,000            + 200       =  76,700 tokens   ← 109× turn 1
```

A typical Claude Code session runs 15–20 turns. At Claude Sonnet pricing ($3/1M tokens), a bloated codebase context costs **$0.23/session**. Multiply by your team. Multiply by daily usage.

And before you even start talking — `package-lock.json` alone is 15,000–120,000 tokens. Every. Single. Session.

---

## Install

```bash
pip install "distill-llm[tiktoken]"   # recommended — exact token counts via tiktoken
pip install "distill-llm[all]"        # + Claude, OpenAI, Gemini adapters + MCP server
pip install distill-llm               # core only — zero hard dependencies
```

---

## CLI

Five commands. Run them in order on any project.

```bash
distill scan     --path .                     # see what's burning tokens + dollar cost
distill analyze  --path .                     # find the waste patterns
distill fix      --path .                     # write .llmignore rules automatically
distill check    --path . --max-pct 30        # CI gate — exits 1 if over budget
distill generate --path . --model all         # generate CLAUDE.md, Modelfile, configs
```

### `distill scan` — find where your money goes

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
  package-lock.json                           122.0k    $0.3660  ← ignoring this = $0.37/session saved
  tsconfig.tsbuildinfo                        103.2k    $0.3096  ← generated, useless to LLM
  src/generated/schema.ts                       4.1k    $0.0123
  src/auth/middleware.ts                        1.8k    $0.0054
```

### `distill fix` — write the rules, show the savings

```bash
distill fix --path .                     # auto-fix HIGH severity patterns
distill fix --path . --dry-run           # preview savings without writing
distill fix --path . --min-severity low  # also catch medium/low patterns
distill fix --path . --model gpt-4o      # price savings against GPT-4o
```

### `distill check` — block context bloat in CI

```bash
distill check --path . --max-pct 30                # fail if > 30% of context
distill check --path . --max-pct 30 --fail-on-waste # also fail on un-ignored lock files
distill check --path . --json                       # machine-readable output
```

**GitHub Actions:**
```yaml
- name: Token budget gate
  run: distill check --path . --max-pct 30 --fail-on-waste
```

### `distill analyze` — understand the root cause

```bash
distill analyze --path .          # full report with fix instructions
distill analyze --path . --fix    # report + apply fixes inline
distill analyze --path . --json   # pipe to your own tooling
```

---

## MCP Server

Install distill as native Claude tools — available in every conversation, no slash commands needed.

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

Claude now has five tools it can call autonomously:

| Tool | What Claude can do with it |
|---|---|
| `scan_tokens` | "Show me which files eat the most tokens" |
| `analyze_context` | "Find waste patterns in this codebase" |
| `fix_context` | "Write the .llmignore rules and show savings" |
| `check_budget` | "Are we within a 30% context budget?" |
| `generate_llmignore` | "Generate ignore rules for this project type" |

**Claude Code slash commands** — drop `.claude/commands/` into any project:

```
/distill-scan     → token audit with dollar costs
/distill-analyze  → waste pattern detection
/distill-fix      → auto-fix with before/after
/distill-check    → CI budget gate
/distill-generate → generate .llmignore
```

→ [Full org deployment guide](docs/mcp-setup.md)

---

## For security teams

Most LLM tooling gives you zero visibility into what files enter model context. Distill gives you:

**Visibility** — `distill scan` shows every file sent to the LLM and its exact token cost. Nothing hidden.

**Secrets stay out** — Generated `.llmignore` blocks `.env`, `.env.*`, `*.pem`, `*.key`, and credential files by default. Lock files, build artifacts, and generated code too.

```
# .llmignore blocks these from ever reaching the LLM
.env
.env.*
*.pem
*.key
*.secret
credentials.json
```

**CI enforcement** — `distill check --fail-on-waste` in your pipeline catches un-ignored lock files and secrets before they hit a PR. Exit 1 blocks the merge.

**Org-wide policy via MCP** — Deploy the MCP server to your dev container image. Every engineer's Claude Desktop and Claude Code session inherits your org's token policy automatically.

**Audit trail** — `.llmignore` is a checked-in, diff-able record of what your LLM is and isn't allowed to read. Review it like any other security config.

---

## How it works

```
  Your codebase
       │
       ▼
  ┌─────────────────────────────────────────────────────────┐
  │  distill scan                                           │
  │  Walks the repo, counts tokens per file (tiktoken       │
  │  cl100k_base or char-ratio fallback), applies pricing   │
  │  per model, respects .llmignore                         │
  └───────────────────────────┬─────────────────────────────┘
                              │ file list + token counts
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │  distill analyze                                        │
  │  Detects patterns: lock files, build output, generated  │
  │  code, test snapshots, oversized files, log files       │
  │  Severity: HIGH / MEDIUM / LOW + exact llmignore rule   │
  └───────────────────────────┬─────────────────────────────┘
                              │ waste patterns
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │  distill fix                                            │
  │  Writes rules to .llmignore, re-scans to get accurate   │
  │  before/after diff, restores on --dry-run               │
  └───────────────────────────┬─────────────────────────────┘
                              │ .llmignore written
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │  distill check  (CI gate)                               │
  │  Compares total tokens vs context limit × max_pct       │
  │  Exit 0 = pass, Exit 1 = block the PR                   │
  └─────────────────────────────────────────────────────────┘
```

**Token counting:** tiktoken `cl100k_base` (exact, same encoder Claude uses) with a character-ratio fallback when tiktoken isn't installed. Zero hard dependencies for core scan/analyze/check.

**Pricing:** Built-in table for Claude, Claude Haiku, Claude Opus, GPT-4o, GPT-4o-mini, Gemini 2.0 Flash, Gemini 1.5 Pro, Ollama (free). All configurable.

---

## Python API

Same interface across every provider — swap LLMs without changing application code.

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

### Prompt caching (Claude)

```python
claude = ClaudeAdapter(model="claude-sonnet-4-5", enable_caching=True)
# Static context (system prompt, docs) is cached automatically
# Cache hit = 90% cheaper than a fresh read
```

### Subagents — research without polluting your context

```python
# Runs in a separate context window — only the summary lands in yours
summary = claude.run_subagent(
    task="How does our auth handle token refresh? Any edge cases?",
    context_files=["src/auth/jwt.ts", "src/middleware/authGuard.ts"]
)
# [Subagent] Research complete — 4,200 tokens used in separate context

response = claude.chat(f"Given: {summary}\nNow add refresh token rotation.")
```

### Lazy file loading

```python
# Warns if file is too large, truncates at line limit
content = llm.load_file_lazy("src/api/routes.ts", max_lines=150)
# [distill] Loaded src/api/routes.ts: 820 tokens

response = llm.chat(f"Add rate limiting:\n{content}")
```

### Add any LLM in ~30 lines

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

Real measurements on real projects. No synthetic data. Reproduction steps in [`benchmarks/results.md`](benchmarks/results.md).

### Token estimation accuracy — tiktoken cl100k_base

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

Top offenders caught: `package-lock.json` (122k tokens), `tsconfig.tsbuildinfo` (103k), test snapshots (4k).

### Compaction savings (10-turn session)

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

## Project structure

```
distill/
├── core/
│   ├── token_counter.py       # Token counting + per-file dollar cost
│   ├── context_analyzer.py    # Waste pattern detection + auto-fixable rules
│   ├── fix.py                 # Auto-apply .llmignore rules, before/after diff
│   ├── check.py               # CI budget gate (exit 0/1)
│   └── cli.py                 # Unified `distill` command dispatcher
│
├── adapters/
│   ├── base_adapter.py        # Abstract base — extend for any LLM in ~30 lines
│   ├── claude_adapter.py      # Prompt caching · subagents · auto-compact
│   ├── openai_adapter.py      # GPT-4o/mini · history trimming · lean prompts
│   ├── gemini_adapter.py      # 1M context · native token counting · caching
│   └── ollama_adapter.py      # Local models · num_ctx tuning · model selection
│
├── distill_mcp/
│   └── server.py              # MCP server — 5 tools for Claude Desktop / Code
│
├── scripts/
│   └── generate_config.py     # Generate .llmignore, CLAUDE.md, Modelfile
│
├── .claude/commands/          # Claude Code slash commands for your team
│   ├── distill-scan.md
│   ├── distill-analyze.md
│   ├── distill-fix.md
│   ├── distill-check.md
│   └── distill-generate.md
│
├── web/                       # Zero-install browser token analyzer
│   └── index.html             # paste code → tokens + cost, quadratic chart
│
└── benchmarks/
    ├── run_benchmarks.py
    └── results.md
```

---

## Supported providers

| Provider | Adapter | Config generated | Key feature |
|---|---|---|---|
| Claude API | `ClaudeAdapter` | system prompt | Prompt caching — up to 90% cost cut on static context |
| Claude Code | — | `CLAUDE.md` + `.claudeignore` | Subagents, `/compact`, lean config |
| GPT-4o / mini | `OpenAIAdapter` | `openai_system.md` | History trimming, any OpenAI-compat endpoint |
| Gemini 2.0 Flash | `GeminiAdapter` | `gemini_system.md` | 1M ctx window, $0.10/1M, native token counting |
| Ollama (local) | `OllamaAdapter` | `Modelfile` | `num_ctx` tuning, task-based model selection |
| LiteLLM / Groq | `OpenAIAdapter(base_url=...)` | OpenAI-compat | Works with any proxy |

---

## The rules that actually move the needle

**1. One batched prompt beats five sequential ones**
```
❌  "Add validation to login"               ✅  "In one pass:
    "Now add it to register"                     1. Add validation to login + register + reset
    "And password reset"                          2. Standardize error messages
    "Update error messages"                       3. Update all affected tests"
    "Update the tests"
```
Five turns = 5× the history accumulation. One turn = none.

**2. `.llmignore` is the single fastest win**
`package-lock.json` = 15,000–120,000 tokens per session. Run `distill fix` once and never pay for it again.

**3. `CLAUDE.md` is a per-session tax**
```
CLAUDE.md size      Cost/session    Cost over 100 sessions
──────────────────  ──────────────  ──────────────────────
 50 lines (~250t)      $0.00075           $0.075
200 lines (~1kt)       $0.003             $0.30
500 lines (~2.5kt)     $0.0075            $0.75
```
Keep it under 80 lines. Use subdirectory `CLAUDE.md` files in monorepos.

**4. Research in a subagent — not your main context**
```python
# ❌ src/auth/ enters your main context and never leaves
claude.chat("Read src/auth/ and explain JWT refresh")

# ✅ Only the summary enters your context
summary = claude.run_subagent("How does JWT refresh work?", ["src/auth/"])
claude.chat(f"Given: {summary}\nNow add refresh token rotation.")
```

**5. Compact between tasks**
History never gets cheaper. Use `/compact` in Claude Code or `llm.compact()` when switching tasks. 42.9% token reduction in a 10-turn session.

---

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

High-value areas:
- `adapters/litellm_adapter.py` — LiteLLM unified proxy
- VS Code extension — real-time token counter in the status bar
- `distill fix` improvements — smarter oversized-file handling
- More test coverage in `tests/`

---

## License

MIT — [LICENSE](LICENSE)

---

<div align="center">

Built after one too many `Claude usage limit reached` messages at 2am.

**If it saved you tokens, drop a ⭐**

</div>
