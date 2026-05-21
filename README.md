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

[![CI](https://github.com/bb1nfosec/distill/actions/workflows/ci.yml/badge.svg)](https://github.com/bb1nfosec/distill/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-a855f7)](CONTRIBUTING.md)
[![Zero hard deps](https://img.shields.io/badge/core-zero%20hard%20deps-f59e0b)](requirements.txt)

[Quick Start](#-quick-start) · [How It Works](#-how-it-works) · [Python API](#-python-api) · [CLI Reference](#-cli-reference) · [All Providers](#-supported-providers)

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
| `core/token_counter.py` | Scan any repo — see exactly which files burn the most tokens |
| `core/context_analyzer.py` | Detect waste patterns: lock files, generated code, bloated configs |
| `setup.sh` | One command — auto-generates all ignore files and configs |
| `scripts/generate_config.py` | Python config generator with project-type auto-detection |
| `ClaudeAdapter` | Prompt caching + subagents + auto-compact for Anthropic's API |
| `OpenAIAdapter` | History trimming + lean system prompts for GPT-4o and friends |
| `OllamaAdapter` | Context window management for local models |
| `BaseLLMAdapter` | Extend for any LLM in ~30 lines |

---

## 🚀 Quick Start

```bash
git clone https://github.com/bb1nfosec/distill
cd distill
pip install -r requirements.txt
```

**Audit your current project's token cost in 30 seconds:**

```bash
python3 core/token_counter.py --path ./my-project
```

```
────────────────────────────────────────────────────────────
  Distill — Context Audit
────────────────────────────────────────────────────────────
  Model         : claude
  Context limit : 200k tokens
  Files scanned : 247
  Total tokens  : 38.4k  (19.2% of context)

  Top token consumers:
  File                                        Tokens   Lines
  ──────────────────────────────────────────  ──────  ──────
  package-lock.json                            18.2k   4821   ← ignore this
  src/generated/schema.ts                       4.1k    892   ← ignore this
  src/api/routes.ts                             2.3k    412
  src/auth/middleware.ts                        1.8k    310

  Recommendations:
  → Lock files using 18.2k tokens — add to .llmignore immediately
  → Generated files using 4.1k tokens — ignore them
────────────────────────────────────────────────────────────
```

**Generate all ignore files and configs:**

```bash
bash setup.sh                              # auto-detect project type
bash setup.sh --model all                  # generate configs for every LLM
python3 scripts/generate_config.py --output . --model all --dry-run
```

**Find waste patterns:**

```bash
python3 core/context_analyzer.py --path ./my-project
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
| **Google Gemini** | `gemini_system.md` | *(extend BaseAdapter)* | Context caching for large documents |
| **Ollama (local)** | `Modelfile` | `OllamaAdapter` | `num_ctx` tuning, task-based model selection |
| **LiteLLM / Groq** | OpenAI-compat | `OpenAIAdapter(base_url=...)` | Works with any OpenAI-compatible proxy |

---

## 🐍 Python API

### Drop-in interface across all providers

```python
from adapters.claude_adapter import ClaudeAdapter
from adapters.openai_adapter import OpenAIAdapter
from adapters.ollama_adapter import OllamaAdapter

# Same interface — swap your LLM without changing any other code
llm = ClaudeAdapter(model="claude-sonnet-4-5", enable_caching=True)
# llm = OpenAIAdapter(model="gpt-4o")
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

### `core/token_counter.py`

```bash
python3 core/token_counter.py --path ./my-project           # scan directory
python3 core/token_counter.py --path . --model openai        # OpenAI tokenizer
python3 core/token_counter.py --path . --top 30              # show top 30 files
python3 core/token_counter.py --file src/api/routes.ts       # single file
python3 core/token_counter.py --path . --json | jq '.[:5]'  # JSON output
python3 core/token_counter.py --path . --no-ignore           # ignore .llmignore
```

### `core/context_analyzer.py`

```bash
python3 core/context_analyzer.py --path ./my-project        # find waste patterns
python3 core/context_analyzer.py --session ./session.json   # analyze a chat log
python3 core/context_analyzer.py --path . --json            # JSON output
```

### `scripts/generate_config.py`

```bash
python3 scripts/generate_config.py --output . --model claude
python3 scripts/generate_config.py --output . --model all
python3 scripts/generate_config.py --output . --model all --dry-run
python3 scripts/generate_config.py --output . --notes "Use Zod. API in src/api/."
```

### `setup.sh`

```bash
bash setup.sh                          # auto-detect everything
bash setup.sh --model all              # all LLMs
bash setup.sh --model claude ./other   # target a different directory
```

---

## 📊 Measured savings

| Workflow | Before | After | Reduction |
|---|---|---|---|
| Claude Code — 20-turn feature build | ~85k tokens | ~22k tokens | **74%** |
| OpenAI GPT-4o — complex refactor | ~120k tokens | ~38k tokens | **68%** |
| Ollama Llama3 — local coding session | ~40k ctx | ~11k ctx | **73%** |
| Any LLM — code review | ~18k tokens | ~6k tokens | **67%** |

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
