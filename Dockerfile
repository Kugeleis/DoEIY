FROM python:3.13-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency configuration
COPY pyproject.toml uv.lock /app/

# Install dependencies (no dev dependencies for production image)
RUN uv sync --frozen --no-dev

# Copy application code
COPY app /app/app
COPY version.txt /app/

# Expose port 3839
EXPOSE 3839

# Run FastAPI app using uvicorn
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3839"]
