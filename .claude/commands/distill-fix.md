Automatically fix context waste in the current project by writing .llmignore rules.

```bash
python3 -m core.fix --path . --min-severity medium
```

Show the before/after token count, percentage of context used, and dollar savings per session. List every rule that was added to .llmignore. If the savings are significant, suggest also running `/distill-generate` to create a full CLAUDE.md.
