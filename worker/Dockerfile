FROM python:3.11-slim

# Install system dependencies, including the RTKLIB package for post-processing RINEX files
RUN apt-get update && apt-get install -y --no-install-recommends \
    rtklib \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy requirements and install using uv
COPY worker/requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy worker and api source code
COPY worker/ /app/
COPY api/ /api/

# Start the worker daemon in unbuffered mode for real-time logging
CMD ["python", "-u", "worker.py"]
