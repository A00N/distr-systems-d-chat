# Use Python 3.14 slim image as base
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy server application files
COPY server/ ./server/

# Create directory for chat logs
RUN mkdir -p /app/data

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose both HTTP and RAFT ports
EXPOSE 9000
EXPOSE 6000

# Set the working directory to server for easier imports
WORKDIR /app/server

# Use environment variable for node ID (will be set at runtime)
CMD ["sh", "-c", "python node.py --id ${DCHAT_NODE_ID:-node} --http-port 9000 --raft-port 6000 --peers ''"]
