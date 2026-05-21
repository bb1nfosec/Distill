#!/usr/bin/env bash
# ============================================================
# LLM Token Optimizer — setup.sh
# Run: bash setup.sh [--model claude|openai|gemini|ollama|all]
# ============================================================
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${2:-$(pwd)}"
MODEL="${1:-auto}"

echo -e "${BOLD}${CYAN}"
echo "  ██╗     ██╗     ███╗   ███╗    ████████╗ ██████╗ ██╗  ██╗███████╗███╗   ██╗"
echo "  ██║     ██║     ████╗ ████║       ██╔══╝██╔═══██╗██║ ██╔╝██╔════╝████╗  ██║"
echo "  ██║     ██║     ██╔████╔██║       ██║   ██║   ██║█████╔╝ █████╗  ██╔██╗ ██║"
echo "  ██║     ██║     ██║╚██╔╝██║       ██║   ██║   ██║██╔═██╗ ██╔══╝  ██║╚██╗██║"
echo "  ███████╗███████╗██║ ╚═╝ ██║       ██║   ╚██████╔╝██║  ██╗███████╗██║ ╚████║"
echo "  ╚══════╝╚══════╝╚═╝     ╚═╝       ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝"
echo -e "  ${NC}${CYAN}OPTIMIZER${NC}"
echo ""

log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
info() { echo -e "${CYAN}→${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }

# ── Detect project type ──────────────────────────────────────
detect_project() {
  local dir="$1"
  if   [[ -f "$dir/package.json" && -f "$dir/next.config.js" ]]; then echo "nextjs"
  elif [[ -f "$dir/package.json" && -d "$dir/src" ]];             then echo "node"
  elif [[ -f "$dir/pyproject.toml" || -f "$dir/setup.py" ]];     then echo "python"
  elif [[ -f "$dir/go.mod" ]];                                    then echo "golang"
  elif [[ -f "$dir/Cargo.toml" ]];                                then echo "rust"
  elif [[ -f "$dir/pubspec.yaml" ]];                              then echo "flutter"
  else echo "generic"
  fi
}

# ── Detect package manager ───────────────────────────────────
detect_pkg_manager() {
  local dir="$1"
  if   [[ -f "$dir/pnpm-lock.yaml" ]]; then echo "pnpm"
  elif [[ -f "$dir/bun.lockb" ]];      then echo "bun"
  elif [[ -f "$dir/yarn.lock" ]];      then echo "yarn"
  elif [[ -f "$dir/package-lock.json" ]]; then echo "npm"
  elif [[ -f "$dir/pyproject.toml" ]]; then
    grep -q "poetry" "$dir/pyproject.toml" 2>/dev/null && echo "poetry" || echo "pip"
  elif [[ -f "$dir/requirements.txt" ]]; then echo "pip"
  else echo "unknown"
  fi
}

# ── Auto-detect model if not specified ──────────────────────
detect_model() {
  if   command -v claude &>/dev/null;       then echo "claude"
  elif [[ -n "$OPENAI_API_KEY" ]];          then echo "openai"
  elif [[ -n "$GEMINI_API_KEY" || -n "$GOOGLE_API_KEY" ]]; then echo "gemini"
  elif command -v ollama &>/dev/null;       then echo "ollama"
  else echo "generic"
  fi
}

# ─────────────────────────────────────────────────────────────
PROJECT_TYPE=$(detect_project "$TARGET_DIR")
PKG_MANAGER=$(detect_pkg_manager "$TARGET_DIR")
[[ "$MODEL" == "auto" ]] && MODEL=$(detect_model)

info "Target directory : $TARGET_DIR"
info "Project type     : $PROJECT_TYPE"
info "Package manager  : $PKG_MANAGER"
info "LLM model        : $MODEL"
echo ""

# ── Generate .llmignore (universal) ─────────────────────────
generate_llmignore() {
  local outfile="$TARGET_DIR/.llmignore"
  cat > "$outfile" << 'EOF'
# .llmignore — files your LLM will skip
# Works with Claude Code (.claudeignore), and any custom LLM tooling

# Dependencies
node_modules/
vendor/
.venv/
venv/
env/
__pycache__/
*.pyc
*.pyo
.eggs/
*.egg-info/

# Build outputs
dist/
build/
out/
.next/
.nuxt/
.svelte-kit/
target/
bin/
obj/

# Lock files (huge, useless for LLM)
package-lock.json
yarn.lock
pnpm-lock.yaml
bun.lockb
Gemfile.lock
poetry.lock
Cargo.lock

# Generated code
src/generated/
*.min.js
*.min.css
*.bundle.js

# Test artifacts
coverage/
.nyc_output/
htmlcov/
__snapshots__/
*.snap

# VCS & IDE
.git/
.svn/
.idea/
.vscode/
*.swp
*.swo

# Logs & temp
*.log
*.tmp
*.cache
.cache/
tmp/
temp/

# Media (not useful as text)
*.png
*.jpg
*.jpeg
*.gif
*.svg
*.ico
*.mp4
*.mp3
*.woff
*.woff2
*.ttf
*.eot

# Infra / config secrets
.env
.env.*
*.pem
*.key
*.cert
secrets/
EOF
  # Append project-specific ignores
  case "$PROJECT_TYPE" in
    nextjs)  echo -e "\n# Next.js\n.vercel/\n.turbo/\nstorybook-static/" >> "$outfile" ;;
    python)  echo -e "\n# Python\nmigrations/\n*.db\n*.sqlite3" >> "$outfile" ;;
    golang)  echo -e "\n# Go\n*.test\n*.prof" >> "$outfile" ;;
    rust)    echo -e "\n# Rust\n*.rlib\n*.rmeta" >> "$outfile" ;;
  esac
  log "Generated .llmignore"
}

# ── Generate CLAUDE.md (Claude Code) ────────────────────────
generate_claude_config() {
  local outfile="$TARGET_DIR/CLAUDE.md"
  local test_cmd="npm test"
  local lint_cmd="npm run lint"
  case "$PKG_MANAGER" in
    pnpm)   test_cmd="pnpm test";   lint_cmd="pnpm typecheck" ;;
    yarn)   test_cmd="yarn test";   lint_cmd="yarn lint" ;;
    bun)    test_cmd="bun test";    lint_cmd="bun run lint" ;;
    poetry) test_cmd="poetry run pytest"; lint_cmd="poetry run ruff check ." ;;
    pip)    test_cmd="pytest";      lint_cmd="ruff check ." ;;
    golang) test_cmd="go test ./..."; lint_cmd="golangci-lint run" ;;
  esac

  cat > "$outfile" << EOF
# Project
- Type: $PROJECT_TYPE
- Package manager: $PKG_MANAGER
- Test: \`$test_cmd\`
- Lint: \`$lint_cmd\`

# Response rules
- Batch all related edits into one pass. Never make partial changes and ask to continue.
- No explanatory prose unless asked. Code + inline comments only.
- Never ask "shall I proceed?" — just execute.
- Read only files directly relevant to the task.
- Keep responses terse. No summaries of what you just did.

# Forbidden paths
- Never read: node_modules/, dist/, build/, .git/, coverage/, generated/

# Research tasks
- For codebase exploration, delegate to a subagent. Return only the summary.

# Session hygiene
- Run /compact after completing each feature or work phase.
- Use /btw for throwaway lookups — keeps them out of context history.
EOF
  log "Generated CLAUDE.md (~$(wc -l < "$outfile") lines)"

  # Symlink .claudeignore → .llmignore
  if [[ -f "$TARGET_DIR/.llmignore" && ! -f "$TARGET_DIR/.claudeignore" ]]; then
    cp "$TARGET_DIR/.llmignore" "$TARGET_DIR/.claudeignore"
    log "Generated .claudeignore (copied from .llmignore)"
  fi
}

# ── Generate OpenAI system prompt ───────────────────────────
generate_openai_config() {
  mkdir -p "$TARGET_DIR/.llm"
  cat > "$TARGET_DIR/.llm/openai_system.md" << EOF
You are a senior engineer assistant. Follow these rules strictly:

**Response rules:**
- Be terse. No preamble, no summaries of what you did.
- Batch all edits. Never make partial changes and ask to continue.
- Code blocks only — no prose explanation unless asked.
- Never ask "shall I proceed?" Just do it.

**Context rules:**
- Only reference files/code explicitly provided in this conversation.
- Do not invent file paths, function names, or imports that weren't shown.
- If unsure what a file contains, ask for its content — don't assume.

**Project: $PROJECT_TYPE ($PKG_MANAGER)**
EOF
  log "Generated .llm/openai_system.md"
}

# ── Generate Gemini system prompt ───────────────────────────
generate_gemini_config() {
  mkdir -p "$TARGET_DIR/.llm"
  cat > "$TARGET_DIR/.llm/gemini_system.md" << EOF
You are a precise, terse engineering assistant.

Rules:
1. Respond with code only unless explanation is explicitly requested.
2. Batch all related changes into a single response.
3. Never ask for confirmation before making changes.
4. Reference only code that has been explicitly shared in this session.
5. Keep all responses as short as possible while being complete.

Project type: $PROJECT_TYPE
Package manager: $PKG_MANAGER
EOF
  log "Generated .llm/gemini_system.md"
}

# ── Generate Ollama Modelfile ────────────────────────────────
generate_ollama_config() {
  mkdir -p "$TARGET_DIR/.llm"
  cat > "$TARGET_DIR/.llm/Modelfile" << 'EOF'
# Ollama Modelfile — token-optimized for coding
# Usage: ollama create mydev -f .llm/Modelfile

FROM llama3.2

# Keep context tight — increase only if needed
PARAMETER num_ctx 8192

# Reduce verbosity
PARAMETER temperature 0.2
PARAMETER top_p 0.9

# Don't keep model loaded forever (saves RAM)
PARAMETER keep_alive 10m

SYSTEM """
You are a terse, precise coding assistant.
- Respond with code only unless explanation is asked.
- Batch all edits in one response.
- No preamble, no summaries.
- Never ask to proceed — just do it.
"""
EOF
  log "Generated .llm/Modelfile (Ollama)"

  cat > "$TARGET_DIR/.llm/ollama_tips.md" << 'EOF'
# Ollama Token Optimization Tips

## Context window
- Default context (2k) is tiny — always set `num_ctx` in Modelfile
- 8k is good for most tasks; 16k for large codebases
- More context = more RAM — tune for your machine

## Model selection by task
| Task | Best model | Context needed |
|---|---|---|
| Quick code edits | llama3.2:3b | 4k |
| Full feature dev | llama3.1:8b | 8k |
| Architecture review | llama3.1:70b (or API) | 16k |
| Local privacy work | mistral:7b | 8k |

## Commands
```bash
# Create optimized model
ollama create mydev -f .llm/Modelfile

# Check context usage
ollama run mydev "/show context"

# Run with custom context size
ollama run llama3.2 --num-ctx 16384
```
EOF
  log "Generated .llm/ollama_tips.md"
}

# ── Install based on selected model ─────────────────────────
echo -e "${BOLD}Installing configs...${NC}"
generate_llmignore

case "$MODEL" in
  claude) generate_claude_config ;;
  openai) generate_openai_config ;;
  gemini) generate_gemini_config ;;
  ollama) generate_ollama_config ;;
  all)
    generate_claude_config
    generate_openai_config
    generate_gemini_config
    generate_ollama_config
    ;;
  generic)
    mkdir -p "$TARGET_DIR/.llm"
    cp "$SCRIPT_DIR/templates/generic/system_prompt.md" "$TARGET_DIR/.llm/system_prompt.md" 2>/dev/null || true
    log "Generated .llm/system_prompt.md (generic)"
    ;;
  *) warn "Unknown model '$MODEL'. Generating generic config."; generate_openai_config ;;
esac

# ── Check Python for token counter ──────────────────────────
echo ""
echo -e "${BOLD}Checking tooling...${NC}"
if command -v python3 &>/dev/null; then
  python3 -c "import tiktoken" 2>/dev/null && log "tiktoken available (accurate token counts)" \
    || warn "tiktoken not installed — run: pip install tiktoken  (for accurate counts)"
  log "python3 available"
else
  warn "python3 not found — token counter won't work. Install Python 3.8+"
fi

# ── Summary ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}Setup complete!${NC}"
echo ""
echo -e "Files created:"
[[ -f "$TARGET_DIR/.llmignore" ]]    && echo -e "  ${GREEN}✓${NC} .llmignore"
[[ -f "$TARGET_DIR/.claudeignore" ]] && echo -e "  ${GREEN}✓${NC} .claudeignore"
[[ -f "$TARGET_DIR/CLAUDE.md" ]]     && echo -e "  ${GREEN}✓${NC} CLAUDE.md"
[[ -f "$TARGET_DIR/.llm/openai_system.md" ]] && echo -e "  ${GREEN}✓${NC} .llm/openai_system.md"
[[ -f "$TARGET_DIR/.llm/gemini_system.md" ]] && echo -e "  ${GREEN}✓${NC} .llm/gemini_system.md"
[[ -f "$TARGET_DIR/.llm/Modelfile" ]] && echo -e "  ${GREEN}✓${NC} .llm/Modelfile"
echo ""
echo -e "Next steps:"
echo -e "  ${CYAN}1.${NC} Audit your token usage:  python3 core/token_counter.py --path ../"
echo -e "  ${CYAN}2.${NC} Review generated files and customize for your project"
echo -e "  ${CYAN}3.${NC} Commit .llmignore and CLAUDE.md (or system prompt) to your repo"
echo -e "  ${CYAN}4.${NC} Read docs/UNIVERSAL_TIPS.md for session habits that save 50-70% more"
echo ""
