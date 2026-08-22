FROM python:3.11-slim

# Install system dependencies (none currently needed for compilation)

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy requirements and install using uv
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy application source code
COPY . .

EXPOSE 8000

# Start FastAPI server using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
