FROM python:3.11-slim

# Install system dependencies
# curl, tar: for downloading rmapi
# git: useful for VCS info if needed (optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tar \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install rmapi (ddvk fork)
# Using v0.0.29 as identified in research
ARG RMAPI_VERSION=v0.0.29
RUN curl -L "https://github.com/ddvk/rmapi/releases/download/${RMAPI_VERSION}/rmapi-linuxx86-64.tar.gz" -o rmapi.tar.gz \
    && tar -xzf rmapi.tar.gz \
    && mv rmapi /usr/local/bin/rmapi \
    && chmod +x /usr/local/bin/rmapi \
    && rm rmapi.tar.gz

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY planner/ planner/
COPY README_REMARKABLE.md .

# Copy and setup entrypoint
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Entrypoint to handle secrets
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["python", "-m", "planner"]
