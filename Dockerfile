FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Runs as root so it can write to the Fly volume mounted at /data (root-owned).
ENV DATA_DIR=/data PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "fitbit_mcp"]
