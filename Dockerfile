# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies with optimized commands to reduce build time
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
    libmagic1 libmagic-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements-clean.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 8000

# Run the application - use Railway PORT environment variable
CMD uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
