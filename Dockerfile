FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/bb1nfosec/skim"
LABEL org.opencontainers.image.description="skim — LLM token proxy and intelligence dashboard"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .

# Install skim with web extras
RUN pip install --no-cache-dir -e ".[web,tiktoken]"

# Default data directory
RUN mkdir -p /data
ENV SKIM_DB_PATH=/data/skim.db

# Expose both ports
# 7474 = proxy (ANTHROPIC_BASE_URL / OPENAI_BASE_URL)
# 7475 = web dashboard
EXPOSE 7474 7475

# Health check via dashboard
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:7475/api/v1/health || exit 1

# Default: start the dashboard server
# Override CMD to run proxy: docker run ... skim proxy --port 7474 --host 0.0.0.0
CMD ["skim", "server", "--port", "7475", "--host", "0.0.0.0"]
