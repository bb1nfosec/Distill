# Twitter/X Thread

Post as a thread. Hook tweet must stand alone — people share the first tweet.

---

**Tweet 1 — Hook (must stop the scroll)**

> Most developers think LLM costs are linear.
>
> They're not. They're quadratic.
>
> Here's what's actually happening in your Claude/GPT sessions: 🧵

---

**Tweet 2 — The insight**

> Every LLM re-reads your ENTIRE conversation on every single turn.
>
> Turn  1:    500 tokens    ($0.001)
> Turn  5:  2,500 tokens    ($0.005)
> Turn 10: 12,000 tokens    ($0.024)  ← 24x turn 1
> Turn 20: 60,000 tokens    ($0.120)  ← 120x turn 1
>
> And most of those tokens? Waste you never asked to send.

---

**Tweet 3 — The real culprit**

> I scanned a real Next.js project with distill:
>
> package-lock.json      → 122,010 tokens  ($0.37/session)
> tsconfig.tsbuildinfo   → 103,206 tokens  ($0.31/session)
> XML schema files       →  67,861 tokens  ($0.20/session)
>
> Total: 1.8M tokens = 938% of Claude's context limit
>
> And this was a perfectly normal project.

---

**Tweet 4 — The fix (30 seconds)**

> distill generates the right .llmignore in one command:
>
> $ distill generate --output . --model all
>
> 561,379 tokens eliminated. $1.68 saved per session.
> Over 100 sessions: $168 saved from a single command.
>
> [attach demo.gif]

---

**Tweet 5 — CI gate**

> You can also wire it into CI so it never silently bloats again:
>
> $ distill check --path . --max-pct 30
>
> Exits 1 if over budget. One line in GitHub Actions.
> Catches the next developer who adds a lock file to context.

---

**Tweet 6 — The compaction insight**

> One more thing most people miss:
>
> Even with a clean codebase, long sessions still go quadratic.
>
> distill check --max-pct 30 in CI +
> /compact between tasks in Claude Code +
> subagents for research =
>
> 42.9% fewer input tokens. Measured. Not estimated.

---

**Tweet 7 — CTA**

> Built distill — open source, zero hard dependencies, works with
> Claude / GPT-4o / Gemini (1M ctx) / Ollama.
>
> Scan your repo in 30 seconds:
> pip install -e ".[tiktoken]" && distill scan --path .
>
> → github.com/bb1nfosec/Distill
> → Try in browser: bb1nfosec.github.io/Distill

---

## Posting notes

- Post tweets 1–3 in quick succession (within 2 minutes). Engagement on tweet 1 determines reach.
- Attach the demo.gif to tweet 4.
- Best time: Tuesday–Thursday 9–11am ET or 6–8pm ET.
- Tag @AnthropicAI on tweet 4 (they retweet Claude tooling regularly).
- Reply to your own thread with "repo + try online" link for easy saving.
- Don't post all 7 back-to-back — X algorithm throttles threads if posted too fast.
  Post 1-3 immediately, 4-5 after 5 min, 6-7 after another 5 min.
