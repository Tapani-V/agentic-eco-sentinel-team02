
# Completed Task List (28-05-2026)

- Set up Python virtual environment (`venv`) and installed all dependencies from `requirements.txt`.
- Created and configured `.env` file for AWS credentials and environment variables.
- Automated IAM role creation for:
	- Agent execution role
	- Lambda tool execution roles
	- ECS/App Runner task execution roles
	- All with permission boundaries for security (via `scripts/iam_setup.py`, `scripts/create_apprunner_ecr_pull_role.py`).
- Created DynamoDB table (`agentic-ai-conversation-memory`) for conversation history and session management (via `scripts/dynamodb_setup.py`, `scripts/main_setup.py`).
- Generated local sensor and spare parts inventory data for MCP tools and agents.
- Automated upload of generated data to AWS S3 for cloud-based tool access.
- Defined JSON schemas for all MCP tools to standardize input/output and integration.
- Developed and deployed two AWS Lambda functions for spare parts lookup and maintenance scheduling.
- Containerized the create_work_order tool as a FastAPI app and pushed the image to AWS ECR.
- Deployed the create_work_order tool as a public HTTPS endpoint using AWS App Runner.
- Verified the public endpoint works with real HTTP requests (curl).
- Updated documentation and checklists to reflect the App Runner-based deployment.
- Ensured all steps are script-driven, minimizing manual AWS Console work.
