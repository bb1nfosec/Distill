# Claude Code - Token Optimization Deep Guide

## How Claude Code consumes tokens

Every Claude Code session has this hidden cost structure:

```
Per-session fixed cost:
  System prompt (Anthropic)    ~3,500 tokens  (you can't change this)
  CLAUDE.md                    varies         (you control this - keep it lean!)

Per-message variable cost:
  Full conversation history    grows quadratically
  File reads (tool calls)      ~5 tokens per line per file
  Tool call overhead           ~180 tokens per call
  Your message                 varies
  Claude's response            varies
```

## The most important thing: keep CLAUDE.md lean

CLAUDE.md is loaded on **every session** and stays in context the entire time. It is never evicted.

```
CLAUDE.md lines   Tokens/session   Cost over 100 sessions
───────────────   ──────────────   ──────────────────────
50  lines           ~250 tokens          25k tokens
100 lines           ~500 tokens          50k tokens
200 lines         ~1,000 tokens         100k tokens  ← "acceptable"
500 lines         ~2,500 tokens         250k tokens  ← wasteful
1000 lines        ~5,000 tokens         500k tokens  ← expensive
```

**Rule: Keep CLAUDE.md under 80 lines.** Only put things Claude needs on EVERY session.

### Good CLAUDE.md (lean)

```markdown
# Project
- Type: Next.js 14 (App Router)
- Package manager: pnpm
- Test: `pnpm test`
- Typecheck: `pnpm typecheck`
- Source: src/app/, src/components/, src/lib/

# Rules
- Batch all edits in one pass. Never partial changes.
- Code only. No explanations unless asked.
- Never ask to proceed - just do it.
- Read only files relevant to the task.

# Forbidden
- node_modules/, .next/, dist/, coverage/, src/generated/

# Research → use subagents. /compact after each feature.
```

### Bad CLAUDE.md (bloated - costs forever)

```markdown
# Project Overview
This is a Next.js project built with... [200 words of prose]

# Architecture
The frontend uses React with... [100 words]

# Coding Standards
We follow these conventions... [500 words]

# API Documentation
Endpoint 1: POST /api/auth/login
  - Takes: { email, password }
  - Returns: { token, user }
  ...

[2000 more lines of docs that belong in a wiki, not CLAUDE.md]
```

## Subdirectory CLAUDE.md files - monorepo strategy

In a monorepo, create CLAUDE.md files in subdirectories. They load **only when Claude navigates into that folder** - not on every session.

```
my-monorepo/
├── CLAUDE.md              ← global rules only (~40 lines)
├── apps/
│   ├── web/
│   │   └── CLAUDE.md      ← Next.js rules, only loads for web work
│   └── api/
│       └── CLAUDE.md      ← FastAPI rules, only loads for API work
└── packages/
    └── ui/
        └── CLAUDE.md      ← Component library rules
```

## Subagents - the most powerful token-saving tool

When you need to research a codebase, **delegate to a subagent**. Subagents run in a completely separate context window and return only a summary to your main conversation.

```
❌ Without subagents:
   "Read all the auth files and tell me how JWT works"
   → Claude reads 10 files × 200 lines = 10,000 tokens injected into YOUR context
   → Those 10,000 tokens are now re-sent on every subsequent message

✅ With subagents:
   "Use a subagent to investigate how JWT refresh works in src/auth/"
   → Subagent reads 10 files in its own context
   → Returns a 500-token summary to you
   → Your context only grew by 500 tokens, not 10,000
```

**How to trigger subagents:**
```
"Use subagents to investigate how authentication handles token refresh"
"Delegate to a subagent: find all places where we call the payments API"
"Use a subagent to read src/db/ and summarize the schema"
```

## /compact - use it strategically

`/compact` summarizes the conversation history, freeing context space.

**When to use it:**
- After completing a feature or task
- When Claude starts making mistakes (context degradation)
- When you see the context indicator climbing past 50%

**How to make it better - add this to CLAUDE.md:**
```markdown
# When compacting, always preserve:
# - The full list of files modified in this session
# - Current task state and what remains
# - Any test commands that were run and their results
```

## /btw - quick lookups without context cost

`/btw` shows an answer in a dismissible overlay that **never enters conversation history**.

```
/btw what's the type signature of useCallback?
/btw is pnpm run or pnpm exec for one-off commands?
/btw what's the shorthand for Object.entries().map()?
```

These don't cost you anything in subsequent turns.

## /clear vs /compact

| Command | What it does | When to use |
|---|---|---|
| `/compact` | Summarizes history into a compressed form | Between tasks in the same session |
| `/clear` | Wipes history completely | When starting a completely new task |

`/compact` > `/clear` in most cases - you keep the task state.

## The batching rule - 60-80% savings alone

Every request re-sends the full conversation. Five small requests cost 5× what one batched request costs.

**Before (5 turns):**
```
"Add validation to the login endpoint"
"Now add it to register too"
"While you're at it, fix password reset"
"Update the error message format"
"Run the tests"
```
Cost: each turn re-sends all previous turns.

**After (1 turn):**
```
"In one pass:
1. Add input validation (Zod) to login, register, and password reset endpoints
2. Standardize error responses to { error: string, field?: string }
3. Run pnpm test after and show results"
```
Cost: ~5× cheaper. Same output quality.

## .claudeignore - essential for every project

```bash
# Auto-generate for your project:
python3 scripts/generate_config.py --output . --model claude
```

The most common high-token offenders:
```
package-lock.json    → often 15,000+ tokens
yarn.lock            → often 10,000+ tokens
src/generated/       → often 5,000–20,000 tokens
dist/, build/        → often 5,000–50,000 tokens
coverage/            → often 3,000+ tokens
```

## Extended thinking - turn it off for simple tasks

Claude runs internal reasoning on every request. For simple, well-defined mechanical tasks (rename this variable, fix this typo, add this import), this is pure waste.

In Claude Code, you can influence this with your prompt phrasing:
- "Mechanically rename all instances of `userId` to `user_id` in src/" → no reasoning needed
- "Design the best architecture for..." → reasoning is valuable

## Session hygiene checklist

Before starting work:
- [ ] Is CLAUDE.md under 80 lines?
- [ ] Is .claudeignore in place?
- [ ] Is this a new task? If yes, start a new session or `/clear`

During work:
- [ ] Batch related changes into single prompts
- [ ] Use `/btw` for quick lookups
- [ ] Use `subagents` for codebase research

After each feature:
- [ ] Run `/compact`
- [ ] Check context indicator - if >60%, consider `/compact` again
