Run the distill CI budget gate against the current project.

```bash
python3 -m core.check --path . --model claude --max-pct 30
```

Report pass or fail, the token percentage used, and the dollar cost per session. If it fails, list which files to add to .llmignore to get under budget.
