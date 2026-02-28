# CachiBot - The Armored AI Agent
# Multi-stage build for Python backend

FROM python:3.12-slim AS backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy build metadata files
COPY pyproject.toml VERSION ./

# hatchling reads readme = "README.md" from pyproject.toml;
# create a placeholder so the install succeeds without requiring
# the actual file in the Docker context.
RUN touch README.md

# Copy application code
COPY cachibot/ ./cachibot/

# Install the package (non-editable)
RUN pip install --no-cache-dir .

# Expose backend port
EXPOSE 5870

CMD ["cachibot", "server"]
