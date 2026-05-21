# Universal LLM Token Optimization Tips

These apply to **every LLM** — Claude, GPT-4, Gemini, Llama, Mistral, anything.

---

## The Core Mental Model

Token costs are **quadratic**, not linear.

Every LLM re-reads the entire conversation on every turn. Turn 10 costs roughly 10x what turn 1 costs in input tokens — because the model re-reads turns 1–9 every time. This is why a long session burns tokens fast.

```
Turn 1:  ~500 tokens
Turn 5:  ~2,500 tokens  (5x)
Turn 10: ~12,000 tokens (24x)
Turn 20: ~60,000 tokens (120x)
```

The fix: **start new sessions for new tasks**. Carry only the state you need.

---

## The 5 Rules That Apply Everywhere

### 1. Batch your prompts

Bad (5 requests, 5x history re-send):
```
"Add input validation to the login function"
"Now add it to the register function"
"Also add it to the password reset flow"
"Fix the error message format while you're at it"
"And update the tests"
```

Good (1 request, 1 history re-send):
```
"Do all of these in one pass:
1. Add input validation to login, register, and password reset
2. Standardize error message format across all three
3. Update tests for each"
```

**Savings: 60-80% on this task alone.**

### 2. Keep your system/config file lean

Every token in your `CLAUDE.md` / `system_prompt` / `Modelfile` system instruction is charged on **every single request forever**. A 5,000-token system prompt at 100 requests = 500,000 extra tokens. For nothing.

- Target: under 200 lines for config files
- Store only what's needed **every** session, not every project fact
- Use lazy-loading / path-scoped configs for project-specific rules

### 3. Tell the LLM exactly what to read

Bad:
```
"Refactor the auth system"
```

Good:
```
"Refactor src/auth/jwt.ts and src/middleware/authGuard.ts.
Do not read other files — the issue is only in those two."
```

Every file the LLM reads = hundreds to thousands of tokens consumed immediately.

### 4. Use a separate context for exploration

When you need the LLM to understand a codebase, use a **fresh context** for the research:
- Claude Code: `use subagents to investigate X` 
- OpenAI: make a separate API call with just the relevant files
- Ollama: new session, paste only the relevant code

Get a summary back. Use that summary in your main task context.

**Why**: codebase exploration reads dozens of files — each one bloats your context for every subsequent message.

### 5. Compact or clear between tasks

After finishing a feature or task:
- **Claude Code**: `/compact` — summarizes history, frees space
- **OpenAI / other**: summarize the conversation yourself and start fresh
- **Ollama**: `/bye` and restart — Ollama has no built-in compaction

---

## LLM-Specific Notes

### Claude Code
- Use `/compact` after each work phase
- Use `/btw` for quick lookups (never enters history)
- Split `CLAUDE.md` into subdirectory files for monorepos
- Subagents are the most powerful tool for context isolation

### OpenAI GPT-4o / GPT-4-turbo
- System prompt is re-sent every request — keep it under 500 tokens
- Use `max_tokens` to cap response length on simple tasks
- GPT-4o-mini is 15x cheaper for tasks that don't need GPT-4o quality

### Gemini 1.5 / 2.0
- 1M+ context window means you can be more liberal, but cost scales linearly
- Use `context caching` for repeated large documents (Gemini API feature)
- Flash models are 10-20x cheaper for most coding tasks

### Ollama (local models)
- **Always set `num_ctx`** — default 2048 is too small for real tasks
- Context is RAM — 8k ctx on llama3.1:8b needs ~6GB VRAM
- Use smaller models (3b) for simple edits, larger for architecture

### Any OpenAI-compatible API (LiteLLM, Groq, Together, etc.)
- Same rules as OpenAI — the protocol is identical
- Check each provider's actual tokenizer — costs vary significantly

---

## Quick Reference: What to do when you're burning tokens

| Symptom | Fix |
|---|---|
| Session getting slow/expensive | `/compact` or start fresh |
| LLM reading irrelevant files | Add to `.llmignore`, be explicit |
| System prompt is huge | Trim to under 200 lines |
| Many small back-and-forths | Batch into one request |
| Exploring a large codebase | Use subagent / fresh context |
| Long explanatory responses | Add "terse" to system prompt |
| Repeating context every message | Add it to system prompt instead |
