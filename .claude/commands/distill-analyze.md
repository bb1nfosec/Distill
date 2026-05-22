Analyze the current project for context waste patterns (lock files, build artifacts, minified assets, etc).

```bash
python3 -m core.context_analyzer --path .
```

List every HIGH and MEDIUM severity pattern found, the tokens wasted, and the exact .llmignore rule to add for each.
