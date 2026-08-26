"""AWS Lambda handler for the full Orchestrator FastAPI application."""

from mangum import Mangum
from .app import app

handler = Mangum(app, lifespan="off")
