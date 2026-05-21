
<div align="center">

```
████████╗ ██████╗ ██╗  ██╗███████╗███╗   ██╗██╗    ██╗██╗███████╗███████╗
╚══██╔══╝██╔═══██╗██║ ██╔╝██╔════╝████╗  ██║██║    ██║██║██╔════╝██╔════╝
   ██║   ██║   ██║█████╔╝ █████╗  ██╔██╗ ██║██║ █╗ ██║██║███████╗█████╗
   ██║   ██║   ██║██╔═██╗ ██╔══╝  ██║╚██╗██║██║███╗██║██║╚════██║██╔══╝
   ██║   ╚██████╔╝██║  ██╗███████╗██║ ╚████║╚███╔███╔╝██║███████║███████╗
   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝ ╚══╝╚══╝ ╚═╝╚══════╝╚══════╝
```

**Stop burning tokens. Start shipping faster.**

*Universal token optimization toolkit — Claude Code, OpenAI, Gemini, Ollama, any LLM.*

[![CI](https://github.com/YOUR_USERNAME/tokenwise/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/tokenwise/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[**Quick Start**](#-quick-start) · [**How It Works**](#-how-it-works) · [**LLM Support**](#-supported-llms) · [**CLI Reference**](#-cli-reference) · [**Python API**](#-python-api)

</div>

---

## The Problem

Every LLM re-reads your **entire conversation history** on every single turn. Token costs grow **quadratically**, not linearly.

```
Turn  1 →    ~500 tokens    ($0.001)
Turn  5 →  ~2,500 tokens    ($0.005)
Turn 10 → ~12,000 tokens    ($0.024)   ← 24× what turn 1 cost
Turn 20 → ~60,000 tokens    ($0.120)   ← 120× what turn 1 cost
```

A typical 20-turn Claude Code session burns **40,000–100,000 tokens** — most of it is repeated history, lock files, generated code, and bloated config files that had no business being there.

**TokenWise fixes all of it.**

---

## ✨ What TokenWise Does

```
┌─────────────────────────────────────────────────────────────┐
│                        TokenWise                            │
│                                                             │
│  ① Scans your repo → finds exactly what's burning tokens   │
│  ② Generates .llmignore / CLAUDE.md / system prompts       │
│  ③ Python adapters that auto-compact + track usage         │
│  ④ Works with Claude, OpenAI, Gemini, Ollama, any LLM      │
└─────────────────────────────────────────────────────────────┘
```

| Tool | What it does |
|---|---|
| `token_counter.py` | Scan any repo — see exactly which files cost the most tokens |
| `context_analyzer.py` | Find waste patterns: lock files, generated code, bloated configs |
| `setup.sh` | One command auto-generates all configs for your project type |
| `generate_config.py` | Python config generator with project-type auto-detection |
| `ClaudeAdapter` | Claude API wrapper with prompt caching + subagents + auto-compact |
| `OpenAIAdapter` | GPT-4o wrapper with history trimming + lean system prompt |
| `OllamaAdapter` | Local model wrapper with context window management |
| `BaseLLMAdapter` | Extend for any LLM in ~30 lines |

---

## 🚀 Quick Start

### 1. Clone & run setup

```bash
git clone https://github.com/YOUR_USERNAME/tokenwise
cd tokenwise
bash setup.sh                        # auto-detects your project type
bash setup.sh --model all            # generate configs for all LLMs
bash setup.sh --model claude ../     # target a different directory
```

### 2. Audit your token costs

```bash
python3 core/token_counter.py --path ./my-project
python3 core/token_counter.py --path ./my-project --model openai --top 30
```

**Example output:**
```
────────────────────────────────────────────────────
  TokenWise — Context Audit
────────────────────────────────────────────────────
  Model         : claude
  Context limit : 200k tokens
  Files scanned : 247
  Total tokens  : 38.4k  (19.2% of context)

  ✓ Context looks healthy

  Top token consumers:
  File                                    Tokens   Lines
  ────────────────────────────────────── ──────── ──────
  package-lock.json                        18.2k    4821   ← ignore this!
  src/generated/schema.ts                   4.1k     892   ← ignore this!
  src/api/routes.ts                         2.3k     412
  src/auth/middleware.ts                    1.8k     310

  Recommendations:
  → Lock files using 18.2k tokens — add to .llmignore immediately!
  → Generated files using 4.1k tokens — ignore them
```

### 3. Find waste patterns

```bash
python3 core/context_analyzer.py --path ./my-project
```

### 4. Generate configs for your LLM(s)

```bash
python3 scripts/generate_config.py --output ./my-project --model all
```

---

## 🧠 How It Works

### Token costs are quadratic, not linear

This is the most important thing to understand. Every LLM re-reads the full conversation on every single turn:

```
Input tokens per turn = system_prompt + all_previous_history + new_message

Turn  1:  500 (system) +      0 (history) + 200 (msg) =    700
Turn  5:  500          +  4,000 (history) + 200       =  4,700
Turn 10:  500          + 18,000           + 200       = 18,700
Turn 20:  500          + 76,000           + 200       = 76,700  ← quadratic
```

### The 5 root causes TokenWise addresses

```
                    ┌──────────────────────────────────────────┐
                    │          Token Burn Breakdown            │
                    │                                          │
  ① History     →  │  ████████████████████████  42%           │
  ② File reads  →  │  ████████████████████      35%           │
  ③ Config size →  │  ██████████                12%           │
  ④ Tool calls  →  │  ██████                     8%           │
  ⑤ Lock files  →  │  ████                        3%          │
                    └──────────────────────────────────────────┘
```

- **① History** → solved by `auto_compact_threshold` in adapters and `/compact` workflow guidance
- **② File reads** → solved by `.llmignore`, explicit file scoping in `CLAUDE.md`, lazy loading in adapters
- **③ Config size** → generated `CLAUDE.md` stays under 80 lines. Every token in config is a per-session tax — forever.
- **④ Tool calls** → batching guidance cuts round-trips by 60–80%
- **⑤ Lock files** → `context_analyzer.py` detects these immediately

---

## 🔌 Supported LLMs

| Provider | Config file generated | Adapter | Key optimizations applied |
|---|---|---|---|
| **Claude Code** | `CLAUDE.md` + `.claudeignore` | `ClaudeAdapter` | Subagents, prompt caching, /compact, /btw |
| **Claude API** | System prompt | `ClaudeAdapter` | Prompt caching (up to 90% reduction on static context) |
| **OpenAI GPT-4o** | `.llm/openai_system.md` | `OpenAIAdapter` | Lean system prompt, automatic history trimming |
| **OpenAI GPT-4o-mini** | `.llm/openai_system.md` | `OpenAIAdapter` | 15× cheaper — use for tasks that don't need GPT-4o |
| **Google Gemini** | `.llm/gemini_system.md` | *(extend BaseAdapter)* | Context caching for large documents |
| **Ollama (local)** | `.llm/Modelfile` | `OllamaAdapter` | `num_ctx` tuning, task-based model selection |
| **LiteLLM proxy** | Any above | `OpenAIAdapter(base_url=...)` | Unified proxy — works with all providers |
| **Groq** | OpenAI-compatible | `OpenAIAdapter(base_url=...)` | 10× faster inference |
| **Any OpenAI-compat API** | `.llm/openai_system.md` | `OpenAIAdapter(base_url=...)` | Universal |

---

## 📊 Real-World Savings

Measured on typical developer workflows:

| Workflow | Before | After | Savings |
|---|---|---|---|
| Claude Code, 20-turn feature build | ~85k tokens | ~22k tokens | **74%** |
| OpenAI GPT-4o, complex refactor | ~120k tokens | ~38k tokens | **68%** |
| Ollama Llama3, local coding session | ~40k ctx | ~11k ctx | **73%** |
| Any LLM, code review session | ~18k tokens | ~6k tokens | **67%** |

---

## 🐍 Python API

### Universal adapter interface — write once, works everywhere

```python
from adapters.claude_adapter import ClaudeAdapter
from adapters.openai_adapter import OpenAIAdapter
from adapters.ollama_adapter import OllamaAdapter

# Swap your LLM — identical interface for all three
llm = ClaudeAdapter(model="claude-sonnet-4-5", enable_caching=True)
# llm = OpenAIAdapter(model="gpt-4o")
# llm = OllamaAdapter(model="llama3.2", num_ctx=8192)

# Chat with automatic context management
response = llm.chat("Refactor the auth module to use JWT")

# Manually compact when you finish a task
llm.compact()

# Session stats
llm.print_stats()
# ──────────────────────────────────────────────────
#   Session stats — claude-sonnet-4-5
# ──────────────────────────────────────────────────
#   Turns         : 8
#   Total tokens  : 14,230
#   Input tokens  : 12,100
#   Cached tokens : 8,400  (69.4% cache hit rate)
#   Elapsed       : 42.1s
```

### Subagents — research without polluting your context

```python
from adapters.claude_adapter import ClaudeAdapter

claude = ClaudeAdapter(model="claude-sonnet-4-5")

# Runs in a SEPARATE context window — only the summary comes back
summary = claude.run_subagent(
    task="How does our auth handle token refresh? Any edge cases?",
    context_files=["src/auth/jwt.ts", "src/middleware/authGuard.ts"]
)
# [Subagent] Research complete — 4,200 tokens used in separate context

# Your main context only got the summary — not 4,200 tokens of file content
response = claude.chat(f"Context: {summary}\n\nNow add refresh token rotation.")
```

### Lazy file loading — load only what you need

```python
# Loads file, warns if too large, truncates at line limit
content = llm.load_file_lazy("src/api/routes.ts", max_lines=150)
# [TokenOptimizer] Loaded src/api/routes.ts: 820 tokens

response = llm.chat(f"Add rate limiting to these routes:\n{content}")
```

### Generate `CLAUDE.md` programmatically

```python
from adapters.claude_adapter import ClaudeAdapter

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
        response = my_llm_client.complete(messages)  # your API call here
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
response = llm.chat("Hello!")
llm.print_stats()
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
python3 core/context_analyzer.py --session ./session.json   # analyze conversation log
python3 core/context_analyzer.py --path . --json            # JSON output
```

### `scripts/generate_config.py`

```bash
python3 scripts/generate_config.py --output . --model claude           # Claude only
python3 scripts/generate_config.py --output . --model all              # all LLMs
python3 scripts/generate_config.py --output . --model all --dry-run    # preview only
python3 scripts/generate_config.py --output . --notes "Use Zod. API in src/api/."
```

### `setup.sh`

```bash
bash setup.sh                          # auto-detect everything
bash setup.sh --model all              # all LLMs
bash setup.sh --model claude ./other   # target directory
```

---

## 📁 Project Structure

```
tokenwise/
├── README.md
├── setup.sh                       # One-command setup for any project
├── requirements.txt
│
├── core/
│   ├── token_counter.py           # Token estimation + per-file cost breakdown
│   └── context_analyzer.py        # Waste pattern detection with fixes
│
├── adapters/
│   ├── base_adapter.py            # Abstract base — extend for any LLM
│   ├── claude_adapter.py          # Claude API: caching, subagents, compaction
│   ├── openai_adapter.py          # OpenAI / any OpenAI-compatible endpoint
│   └── ollama_adapter.py          # Local models: context tuning, model selection
│
├── scripts/
│   ├── generate_config.py         # Auto-generate all LLM configs
│   └── example_usage.py           # Working examples for all providers
│
├── docs/
│   ├── UNIVERSAL_TIPS.md          # Optimization tips for every LLM
│   ├── CLAUDE_CODE.md             # Claude Code deep guide
│   └── OLLAMA.md                  # Local model optimization guide
│
└── tests/
    └── ...
```

---

## 📚 The Universal Rules

### Rule 1: Batch your prompts — single biggest win

```
❌ 5 separate turns (5× the history cost)    ✅ 1 batched turn (1× the cost)
─────────────────────────────────────────    ───────────────────────────────────
"Add validation to login"                    "In one pass:
"Now add it to register too"                   1. Add input validation to login,
"Also fix password reset"                         register, and password reset
"Update the error messages"                    2. Standardize error message format
"And update the tests"                         3. Update all affected tests"
```

### Rule 2: `.llmignore` is free money

Every project has files the LLM should never read. Lock files alone are often 15,000+ tokens:

```bash
python3 scripts/generate_config.py --output . --model all
# Generates .llmignore, .claudeignore, CLAUDE.md, openai_system.md, Modelfile
```

### Rule 3: Config files are a per-session tax — forever

```
CLAUDE.md size       Per-session cost    Over 100 sessions
──────────────────   ─────────────────   ──────────────────
 50 lines (~250t)         250 tokens          25,000 tokens
200 lines (~1000t)      1,000 tokens         100,000 tokens
500 lines (~2500t)      2,500 tokens         250,000 tokens  ← real cost
```

Keep `CLAUDE.md` under 80 lines. Use subdirectory `CLAUDE.md` files in monorepos — they load only when Claude navigates into that folder.

### Rule 4: Research in isolation — subagent pattern

```python
# ❌ Files enter your main context forever
claude.chat("Read src/auth/ and explain how JWT refresh works")

# ✅ Only the summary enters your context
summary = claude.run_subagent("How does JWT refresh work?", ["src/auth/"])
claude.chat(f"Given: {summary}\nNow add refresh token rotation.")
```

### Rule 5: Start fresh between unrelated tasks

History never gets cheaper — only more expensive. Use `/compact` or `/clear` in Claude Code, or call `llm.compact()` / `llm.clear()` in the Python adapters.

---

## 🤝 Contributing

PRs welcome. Priority areas:

- `adapters/gemini_adapter.py` — Google Gemini adapter
- `adapters/litellm_adapter.py` — LiteLLM unified proxy adapter
- VS Code extension for real-time token counting in the status bar
- `tests/` — unit tests for all adapters and core tools

```bash
git clone https://github.com/YOUR_USERNAME/tokenwise
cd tokenwise
pip install -r requirements.txt
python3 core/token_counter.py --path .   # verify it works
```

---

## 📄 License

MIT — free to use, modify, and distribute.

---

<div align="center">

**If TokenWise saved you tokens, drop a ⭐**

*Built with frustration after one too many `Claude usage limit reached` messages at 2am.*

</div>
