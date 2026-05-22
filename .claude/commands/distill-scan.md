Scan the current project for token usage and dollar cost.

Run the following and report the results:

```bash
python3 -m core.token_counter --path . --model claude
```

Summarize: total tokens, % of context used, per-session dollar cost, and the top 5 heaviest files. Flag anything over 10% of context as a candidate to add to .llmignore.
