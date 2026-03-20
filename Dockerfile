FROM python:3.12.10-slim

WORKDIR /app

# Create a non-root user to run the application
RUN useradd --create-home --shell /bin/bash appuser

# Copy all project files
COPY pyproject.toml .
COPY src/ src/

# Install the package and its dependencies
RUN pip install --no-cache-dir .

# Create data directory for token persistence
RUN mkdir -p /data && chown appuser:appuser /data

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["python", "-m", "fitbit_mcp"]
