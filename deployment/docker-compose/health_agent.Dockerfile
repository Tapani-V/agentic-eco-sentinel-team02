FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY src/services/health_agent/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project (for src imports)
COPY . .

# Load environment
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8001/health')"

# Run service
CMD ["python", "-m", "uvicorn", "src.services.health_agent.app:app", "--host", "0.0.0.0", "--port", "8001"]
