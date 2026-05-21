.PHONY: help install test lint scan analyze clean

help:
	@echo ""
	@echo "  distill — available commands"
	@echo ""
	@echo "  make install     Install all dependencies"
	@echo "  make install-min Install core deps only (tiktoken + pytest)"
	@echo "  make test        Run test suite"
	@echo "  make scan        Token-count this repo (self-audit)"
	@echo "  make analyze     Find waste patterns in this repo"
	@echo "  make configs     Generate all LLM configs for current directory"
	@echo "  make lint        Run ruff linter"
	@echo "  make clean       Remove __pycache__ and .pyc files"
	@echo ""

install:
	pip install -r requirements.txt

install-min:
	pip install tiktoken pytest

test:
	pytest tests/ -v

scan:
	python3 core/token_counter.py --path . --model claude --top 20

analyze:
	python3 core/context_analyzer.py --path .

configs:
	python3 scripts/generate_config.py --output . --model all --dry-run

lint:
	ruff check . --fix

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
