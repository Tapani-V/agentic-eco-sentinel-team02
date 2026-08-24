FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/

# Load environment
ENV PYTHONUNBUFFERED=1

# AgentCore Runtime requires the container to serve HTTP on port 8080
# (POST /invocations, GET /ping) - see bedrock_agentcore.runtime.BedrockAgentCoreApp
EXPOSE 8080

# Health check against the AgentCore Runtime /ping endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# handler.py is itself the BedrockAgentCoreApp - no wrapper script needed
CMD ["python", "-m", "src.services.diagnosis_agent.handler"]
