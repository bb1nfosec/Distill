<div align="center">

```
 ██████╗ ██╗███████╗████████╗██╗██╗     ██╗
 ██╔══██╗██║██╔════╝╚══██╔══╝██║██║     ██║
 ██║  ██║██║███████╗   ██║   ██║██║     ██║
 ██║  ██║██║╚════██║   ██║   ██║██║     ██║
 ██████╔╝██║███████║   ██║   ██║███████╗███████╗
 ╚═════╝ ╚═╝╚══════╝   ╚═╝   ╚═╝╚══════╝╚══════╝
```

### Stop burning tokens. Start shipping faster.

*Universal token optimization toolkit — Claude, OpenAI, Gemini, Ollama, any LLM.*

[![PyPI](https://img.shields.io/pypi/v/distill-llm?color=0073b7&logo=pypi&logoColor=white)](https://pypi.org/project/distill-llm/)
[![CI](https://github.com/bb1nfosec/distill/actions/workflows/ci.yml/badge.svg)](https://github.com/bb1nfosec/distill/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-a855f7)](CONTRIBUTING.md)
[![Zero hard deps](https://img.shields.io/badge/core-zero%20hard%20deps-f59e0b)](requirements.txt)

[Quick Start](#-quick-start) · [Try Online](https://bb1nfosec.github.io/Distill) · [Benchmarks](#-benchmarks) · [How It Works](#-how-it-works) · [Python API](#-python-api) · [CLI Reference](#-cli-reference)

![distill demo](assets/demo.gif)

</div>

---

## The Problem

Every LLM re-reads your **entire conversation history** on every single turn. Token costs grow quadratically, not linearly — and most of that cost is lock files, generated code, and bloated config files that should never have been there.

```
Turn  1 →    ~500 tokens    ($0.001)
Turn  5 →  ~2,500 tokens    ($0.005)
Turn 10 → ~12,000 tokens    ($0.024)   ← 24× what turn 1 cost
Turn 20 → ~60,000 tokens    ($0.120)   ← 120× what turn 1 cost
```

A typical 20-turn Claude Code session burns **40,000–100,000 tokens**. Distill fixes all of it.

---

## ✦ What Distill Does

| Tool | What it does |
|---|---|
| `distill scan` | Scan any repo — tokens **and dollar cost** per file |
| `distill analyze` | Detect waste: lock files, generated code, bloated configs |
| `distill check` | CI budget gate — exits 1 if over context threshold |
| `distill generate` | Auto-generate `.llmignore`, `CLAUDE.md`, and LLM configs |
| `ClaudeAdapter` | Prompt caching + subagents + auto-compact for Anthropic's API |
| `OpenAIAdapter` | History trimming + lean system prompts for GPT-4o and friends |
| `GeminiAdapter` | 1M context window, token counting via native API |
| `OllamaAdapter` | Context window management for local models |
| `BaseLLMAdapter` | Extend for any LLM in ~30 lines |

---

## 🚀 Quick Start

```bash
pip install "distill-llm[tiktoken]"   # tiktoken optional but recommended for exact counts
```

**Audit your project's token cost and dollar spend in 30 seconds:**

```bash
distill scan --path ./my-project
```

```
──────────────────────────────────────────────────────────────
  distill — Context Audit
──────────────────────────────────────────────────────────────
  Model         : claude  ($3.00 / 1M input tokens)
  Context limit : 200k tokens
  Files scanned : 247
  Total tokens  : 38.4k  (19.2% of context)
  Per-session $ : $0.1152  (input cost, context loaded once)
  Sessions / $1 : 8

  File                                        Tokens   Lines     Cost
  ──────────────────────────────────────────  ──────  ──────  ──────
  package-lock.json                            18.2k   4821   $0.0547  ← ignore
  src/generated/schema.ts                       4.1k    892   $0.0123  ← ignore
  src/api/routes.ts                             2.3k    412   $0.0069
  src/auth/middleware.ts                        1.8k    310   $0.0054

  Recommendations:
  → Lock files: 18.2k tokens ($0.0547) — add to .llmignore
  → Generated files: 4.1k tokens — ignore them
──────────────────────────────────────────────────────────────
```

**Find waste and set a CI budget gate:**

```bash
distill analyze --path ./my-project
distill check   --path . --max-pct 30           # exits 1 if over 30% of context
distill check   --path . --max-pct 30 --fail-on-waste   # also fail on lock files etc.
```

**Generate all ignore files and configs:**

```bash
distill generate --output . --model all         # .llmignore, CLAUDE.md, Modelfile, …
distill generate --output . --model all --dry-run
```

---

## 🧠 How It Works

### Why costs are quadratic

```
Input tokens per turn = system_prompt + all_previous_history + new_message

Turn  1:   500 (system) +       0 (history) + 200 (msg) =     700
Turn  5:   500          +   4,000            + 200       =   4,700
Turn 10:   500          +  18,000            + 200       =  18,700
Turn 20:   500          +  76,000            + 200       =  76,700
```

### The five root causes — and their fixes

```
  ① Conversation history  ████████████████████████  42%  →  auto_compact + /compact
  ② Large file reads      ████████████████████      35%  →  .llmignore + lazy loading
  ③ Bloated config files  ██████████                12%  →  generated CLAUDE.md ≤ 80 lines
  ④ Tool call overhead    ██████                     8%  →  batching guidance
  ⑤ Lock / build files    ████                       3%  →  context_analyzer.py
```

---

## 🔌 Supported Providers

| Provider | Config generated | Adapter | Key optimizations |
|---|---|---|---|
| **Claude API** | System prompt | `ClaudeAdapter` | Prompt caching — up to 90% cost reduction on static context |
| **Claude Code** | `CLAUDE.md` + `.claudeignore` | — | Subagents, `/compact`, `/btw`, lean config |
| **OpenAI GPT-4o** | `openai_system.md` | `OpenAIAdapter` | Lean system prompt, automatic history trimming |
| **OpenAI GPT-4o-mini** | `openai_system.md` | `OpenAIAdapter` | 15× cheaper — use for tasks that don't need full GPT-4o |
| **Google Gemini** | `gemini_system.md` | `GeminiAdapter` | 1M ctx window, native token counting, context caching |
| **Ollama (local)** | `Modelfile` | `OllamaAdapter` | `num_ctx` tuning, task-based model selection |
| **LiteLLM / Groq** | OpenAI-compat | `OpenAIAdapter(base_url=...)` | Works with any OpenAI-compatible proxy |

---

## 🐍 Python API

### Drop-in interface across all providers

```python
from adapters import ClaudeAdapter, OpenAIAdapter, GeminiAdapter, OllamaAdapter

# Same interface — swap your LLM without changing any other code
llm = ClaudeAdapter(model="claude-sonnet-4-5", enable_caching=True)
# llm = OpenAIAdapter(model="gpt-4o")
# llm = GeminiAdapter(model="gemini-2.0-flash")   # $0.10/1M, 1M ctx window
# llm = OllamaAdapter(model="llama3.2", num_ctx=8192)

response = llm.chat("Refactor the auth module to use JWT")

# Compact when you finish a task phase
llm.compact()

# Session stats
llm.print_stats()
# ──────────────────────────────────────────────
#   Session stats — claude-sonnet-4-5
# ──────────────────────────────────────────────
#   Turns         : 8
#   Total tokens  : 14,230
#   Input tokens  : 12,100
#   Cached tokens : 8,400  (69.4% hit rate)
#   Elapsed       : 42.1s
```

### Subagents — research without polluting your context

```python
claude = ClaudeAdapter(model="claude-sonnet-4-5")

# Runs in a separate context window — only the summary lands in yours
summary = claude.run_subagent(
    task="How does our auth handle token refresh? Any edge cases?",
    context_files=["src/auth/jwt.ts", "src/middleware/authGuard.ts"]
)
# [Subagent] Research complete — 4,200 tokens used in separate context

response = claude.chat(f"Context: {summary}\n\nNow add refresh token rotation.")
```

### Lazy file loading

```python
# Loads file, warns if too large, truncates at line limit
content = llm.load_file_lazy("src/api/routes.ts", max_lines=150)
# [TokenOptimizer] Loaded src/api/routes.ts: 820 tokens

response = llm.chat(f"Add rate limiting:\n{content}")
```

### Generate a lean `CLAUDE.md`

```python
config = ClaudeAdapter.generate_claude_md(
    project_type="nextjs",
    pkg_manager="pnpm",
    test_cmd="pnpm test",
    lint_cmd="pnpm typecheck",
    forbidden_dirs=["node_modules", ".next", "dist", "coverage"],
    custom_notes="Use Zod for all validation. API handlers in src/app/api/.",
)
# Result: ~65 lines, ~320 tokens — lean by design
```

### Add any LLM in ~30 lines

```python
from adapters.base_adapter import BaseLLMAdapter, CompletionResult

class MyLLMAdapter(BaseLLMAdapter):
    def count_tokens(self, text: str) -> int:
        return len(text) // 4  # or use your provider's tokenizer

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

# Instantly gets: auto-compact, history management, stats, lazy loading
llm = MyLLMAdapter(model="my-model-v1", auto_compact_threshold=0.70)
```

---

## 🖥️ CLI Reference

Install once and use `distill` everywhere:

```bash
pip install "distill-llm[tiktoken]"
```

### `distill scan`

```bash
distill scan --path ./my-project              # tokens + cost per file
distill scan --path . --model gpt-4o          # OpenAI pricing
distill scan --path . --top 30                # top 30 files
distill scan --file src/api/routes.ts         # single file
distill scan --path . --json | jq '.[:5]'     # pipe to jq
distill scan --path . --no-ignore             # skip .llmignore
```

### `distill analyze`

```bash
distill analyze --path ./my-project           # find waste patterns
distill analyze --path . --json               # JSON output for scripting
```

### `distill check`  ← use in CI

```bash
distill check --path . --max-pct 30           # fail if > 30% of context
distill check --path . --max-pct 50 --model gpt-4o
distill check --path . --max-pct 30 --fail-on-waste   # also fail on lock files
distill check --path . --json                 # machine-readable exit + report
```

**GitHub Actions:**
```yaml
- name: Token budget check
  run: distill check --path . --max-pct 30
```

### `distill generate`

```bash
distill generate --output . --model all          # .llmignore, CLAUDE.md, Modelfile
distill generate --output . --model claude        # Claude only
distill generate --output . --model all --dry-run # preview without writing
```

### Direct scripts (no install required)

```bash
python3 core/token_counter.py --path .
python3 core/context_analyzer.py --path .
python3 core/check.py --path . --max-pct 30
python3 scripts/generate_config.py --output . --model all
```

---

## 📊 Benchmarks

Real measurements. No mocks. Full results and reproduction steps in [`benchmarks/results.md`](benchmarks/results.md).

### Token estimation accuracy

Distill uses tiktoken's `cl100k_base` encoder. Across every file type tested — inline comments, full adapters, 50 KB lock file slices, large Python files — error vs ground truth is **0.00%**.

| Sample | Chars | Error | Time |
|---|---:|---:|---:|
| Inline comment             |       41 | **0.0%** |  8.5 ms |
| Full adapter file (~8 KB)  |    7,768 | **0.0%** |  1.1 ms |
| Lock file slice (50 KB)    |   50,000 | **0.0%** |  9.7 ms |
| Large Python file (~35 KB) |   35,000 | **0.0%** |  5.0 ms |

### Scan throughput

| Project | Files | Tokens | Time | Throughput |
|---|---:|---:|---:|---:|
| distill (this repo, small)     |    26 |     33,374 |   21 ms | 1,264 files/s · 1.62 M tok/s |
| TradingAgents (Python, medium) |    85 |     85,412 |   51 ms | 1,655 files/s · 1.66 M tok/s |
| vaathi-main (Next.js, large)   |   520 | 1,876,732 | 1,028 ms |   506 files/s · 1.83 M tok/s |

### .llmignore waste elimination — vaathi-main (real Next.js project)

| | Tokens | % of Claude 200k context |
|---|---:|---:|
| Before `.llmignore` | 1,876,732 | **938.4%** (9× over limit) |
| After `.llmignore`  | 1,315,353 | 657.7% |
| **Eliminated**      | **561,379** | **29.9%** |

Top waste found: `package-lock.json` (122k tokens), `tsconfig.tsbuildinfo` (103k), XML schema files (160k+).

### Compaction — input tokens per turn (10-turn session)

Compaction applied at turn 4, compressing history to ~18%:

| | Input tokens |
|---|---:|
| 10 turns without compaction | 37,760 |
| 10 turns with compaction    | 21,572 |
| **Saved**                   | **16,188 (42.9%)** |

```bash
# Reproduce all benchmarks yourself
python3 benchmarks/run_benchmarks.py
python3 benchmarks/run_benchmarks.py --path /your/project
```

---

## 📁 Project Structure

```
distill/
├── core/
│   ├── token_counter.py        # Token estimation + per-file cost breakdown
│   └── context_analyzer.py     # Waste pattern detection with actionable fixes
│
├── adapters/
│   ├── base_adapter.py         # Abstract base — extend for any LLM
│   ├── claude_adapter.py       # Claude: prompt caching, subagents, compaction
│   ├── openai_adapter.py       # OpenAI / any OpenAI-compatible endpoint
│   └── ollama_adapter.py       # Local models: context tuning, model selection
│
├── scripts/
│   ├── generate_config.py      # Auto-generate all LLM configs
│   └── example_usage.py        # Working examples for all providers
│
├── docs/
│   ├── UNIVERSAL_TIPS.md       # Optimization tips for every LLM
│   ├── CLAUDE_CODE.md          # Claude Code deep guide
│   └── OLLAMA.md               # Local model guide
│
├── tests/
│   └── test_core.py
│
├── setup.sh                    # One-command project setup
└── requirements.txt
```

---

## 💡 The Rules That Matter Most

### 1. Batch your prompts — single biggest win

```
❌  5 separate turns                    ✅  1 batched turn
──────────────────────────────────      ────────────────────────────────────
"Add validation to login"               "In one pass:
"Now add it to register too"              1. Add input validation to login,
"Also fix password reset"                    register, and password reset
"Update the error messages"               2. Standardize error message format
"And update the tests"                    3. Update all affected tests"
```

### 2. `.llmignore` is free money

Lock files alone are often 15,000+ tokens per session. One command generates everything:

```bash
python3 scripts/generate_config.py --output . --model all
```

### 3. Config files are a per-session tax

```
CLAUDE.md size        Per-session cost   Over 100 sessions
────────────────────  ─────────────────  ──────────────────
 50 lines  (~250t)          250 tokens        25,000 tokens
200 lines (~1,000t)       1,000 tokens       100,000 tokens
500 lines (~2,500t)       2,500 tokens       250,000 tokens
```

Keep `CLAUDE.md` under 80 lines. Use subdirectory files in monorepos.

### 4. Research in isolation

```python
# ❌ Files enter your main context forever
claude.chat("Read src/auth/ and explain JWT refresh")

# ✅ Only the summary enters your context
summary = claude.run_subagent("How does JWT refresh work?", ["src/auth/"])
claude.chat(f"Given: {summary}\nNow add refresh token rotation.")
```

### 5. Start fresh between unrelated tasks

History never gets cheaper. Use `/compact` in Claude Code or `llm.compact()` / `llm.clear()` when switching tasks.

---

## 🤝 Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

Priority areas:
- `adapters/gemini_adapter.py` — Google Gemini adapter
- `adapters/litellm_adapter.py` — LiteLLM unified proxy adapter
- VS Code extension — real-time token counter in the status bar
- More tests in `tests/`

---

## 📄 License

MIT — free to use, modify, and distribute. See [LICENSE](LICENSE).

---

<div align="center">

**If Distill saved you tokens, drop a ⭐**

*Built with frustration after one too many `Claude usage limit reached` messages at 2am.*

</div>
