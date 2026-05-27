# distill MCP Server - Org Setup Guide

Adds `scan_tokens`, `check_budget`, `analyze_context`, and `generate_llmignore` as native Claude tools available in every conversation.

## Install

```bash
pip install "distill-llm[mcp]"
```

## Configure

### Claude Desktop (Mac/Windows)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "distill": {
      "command": "distill-mcp"
    }
  }
}
```

Restart Claude Desktop. The tools appear automatically.

### Claude Code (CLI)

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "distill": {
      "command": "distill-mcp"
    }
  }
}
```

Or add globally in `~/.claude/mcp.json` to enable across all projects.

### VS Code / JetBrains (Claude Code extension)

Same `.mcp.json` approach - Claude Code picks it up from the project root automatically.

## Tools available to Claude

| Tool | What it does |
|---|---|
| `scan_tokens` | List all files by token count + dollar cost |
| `check_budget` | CI gate - pass/fail against a context % budget |
| `analyze_context` | Detect lock files, build artifacts, minified assets |
| `generate_llmignore` | Generate `.llmignore` rules for the project type |

## Usage examples

Once configured, just ask Claude:

> "Scan this project's token usage"
> "Check if we're within a 30% context budget"
> "What's wasting tokens in this codebase?"
> "Generate a .llmignore for this repo"

Claude will call the tools automatically - no slash commands needed.

## Slash commands (Claude Code only)

For teams using Claude Code CLI, copy the commands from `.claude/commands/` into your project:

```bash
cp -r .claude/commands/ your-project/.claude/commands/
```

Then use `/distill-scan`, `/distill-check`, `/distill-analyze`, `/distill-generate` in any Claude Code session.

## Organization-wide deployment

For org-wide rollout without per-machine installs, add distill-mcp to your shared dev container or CI image:

```dockerfile
RUN pip install "distill-llm[mcp]"
```

Then distribute `.mcp.json` via your dotfiles repo or onboarding script.
