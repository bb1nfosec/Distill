# Show HN Submission

**URL to submit:** https://github.com/bb1nfosec/Distill

---

## Title (pick one — A/B test if possible)

**Option A (most specific, best CTR pattern):**
> Show HN: I built a CLI that shows which files are burning your Claude/GPT-4 tokens — and the dollar cost

**Option B (problem-first framing):**
> Show HN: LLM token costs grow quadratically. Here's a tool that shows you exactly why and how to fix it

**Option C (number hook):**
> Show HN: distill — scan your codebase and see which files cost $0.05+ per Claude session

---

## Body text

Token costs aren't linear — they're quadratic. Every LLM re-reads your entire conversation history on every turn. A 20-turn Claude session can cost 120× more than turn 1 because the model ingests all previous history every time.

Most of that cost is waste: lock files (package-lock.json alone is often 120k tokens = $0.36/session), generated code, tsconfig.tsbuildinfo, XML schemas. Files the LLM should never see.

distill scans your repo and shows you exactly what's burning tokens and what it costs per session:

```
distill scan --path ./my-project

  distill — Context Audit
  Model         : claude  ($3.00 / 1M input tokens)
  Total tokens  : 1.8M  (938.4% of context)
  Per-session $ : $5.64  ← most of this is waste

  package-lock.json      122,010 tokens   $0.3660
  tsconfig.tsbuildinfo   103,206 tokens   $0.3096
  schemas/sml.xsd         67,861 tokens   $0.2036
```

Then generates the right .llmignore/CLAUDE.md to eliminate the waste:

```
distill generate --output . --model all
→ Eliminated 561,379 tokens ($1.68/session)
```

And a CI gate so it never silently bloats again:

```
distill check --path . --max-pct 30
# exits 1 if over budget — works in GitHub Actions
```

Adapters for Claude (with prompt caching), OpenAI, Gemini (1M ctx), and Ollama. Core tools have zero hard dependencies.

Benchmarks in the repo: 0.00% token estimation error, 42.9% input reduction with compaction.

---

## Timing advice

- Post Tuesday–Thursday, 8–10am ET (peak HN technical traffic)
- Do not edit the title after posting
- First 30 minutes determine front page. Be ready to respond to comments immediately.
- Expect: questions about tiktoken accuracy, whether it works with LangChain, whether there's a VS Code extension
