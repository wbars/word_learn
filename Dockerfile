FROM python:3.11-slim

# Ensure Python output is unbuffered for proper logging
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Run database migrations and start bot
CMD ["sh", "-c", "alembic upgrade head && python -m word_learn.bot"]
