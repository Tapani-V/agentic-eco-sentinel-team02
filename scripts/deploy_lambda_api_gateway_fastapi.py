#!/usr/bin/env python3
"""
Deploy the FastAPI+Mangum Orchestrator Lambda + REST API Gateway (boto3, no SAM/CFN)

This is the team-parameterized deploy script for functions/api_gateway_handler.py
(the FastAPI app exposing /devices, /fleet-summary, /alerts, /work-orders,
/maintenance-schedule, /spare-parts, /analytics/*, /orchestrate, /health), which is
DIFFERENT from the older scripts/deploy_lambda_api_gateway_boto3.py (that one
targets the original single-file functions/lambda_orchestrator_handler.py handler
directly and is not used by the current Frankfurt/team01 stack).

Mirrors the exact live team01 setup in eu-central-1 (Lambda name, IAM role/policy
names/shapes, REST API structure) verified via AWS CLI on 2026-08-28, generalized
by TEAM_ID.

What this script creates/updates (idempotent - safe to re-run):
    1. IAM role "<team_id>-lambda-execution-role" with inline policies:
       - "<team_id>-agentcore-invoke"        (bedrock-agentcore:* to call the runtime)
       - "<team_id>-lambda-policy"           (logs + DynamoDB conversation-memory table)
       - "<team_id>-s3-synthetic-data-access" (S3 read on "<team_id>-synthetic-data")
    2. Lambda function "<team_id>-orchestrator-handler"
       - Handler: api_gateway_handler.handler (Mangum-wrapped FastAPI app)
       - Packages functions/*.py + fastapi/mangum/boto3 dependencies
       - Env vars: ORCHESTRATOR_RUNTIME_ID, AGENTCORE_MEMORY_ID, AWS_REGION_NAME, LOG_LEVEL
         (NOT Cognito-related - this Lambda calls the orchestrator via IAM/SigV4
         boto3.invoke_agent_runtime(), not through the MCP gateway)
    3. REST API "<team_id>-orchestrator-api" (REGIONAL), resources "/" and "/{proxy+}"
       both ANY-method AWS_PROXY integrations to the Lambda (this single catch-all
       covers every FastAPI route, including /orchestrate, so no extra resources
       are needed beyond what team01 effectively uses).
    4. Lambda resource-based permission allowing this API to invoke the function.
    5. Deploys stage "prod".

Prerequisites this script does NOT create (must already exist - see other scripts):
    - AgentCore Runtimes already deployed for this team_id
      (scripts/deploy_to_agentcore_boto3.py) -> reads their runtime ID from
      agent_endpoints.<team_id>.json.
    - DynamoDB table "<team_id>-conversation-memory" and S3 bucket
      "<team_id>-synthetic-data" (scripts/dynamodb_setup.py / setup_s3_synthetic_data.py)
      - only their ARNs are referenced by the IAM policy here, not created here.

AgentCore Memory (scripts/deploy_agentcore_memory.py) is NOT part of the current
setup - AGENTCORE_MEMORY_ID is looked up on a best-effort basis and left blank
("") if no matching memory resource exists, rather than failing the deploy.

Usage:
    python scripts/deploy_lambda_api_gateway_fastapi.py --team-id team02 \\
        [--region eu-central-1] [--profile StandardAccess-450410489798]

Output:
    api_gateway_endpoints.<team_id>.json - the REST API's id/domain/stage, to feed
    into scripts/deploy_cloudfront.py's API_GATEWAY_DOMAIN/API_GATEWAY_STAGE_PATH.
"""

import argparse
import io
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("DEPLOY_LAMBDA_APIGW")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS_DIR = PROJECT_ROOT / "functions"
LAMBDA_RUNTIME = "python3.11"
LAMBDA_HANDLER = "api_gateway_handler.handler"
STAGE_NAME = "prod"


class LambdaApiGatewayDeployer:
    def __init__(self, team_id: str, region: str, profile: str):
        self.team_id = team_id
        self.region = region
        self.profile = profile

        session = boto3.Session(profile_name=profile, region_name=region)
        self.iam = session.client("iam", region_name=region)
        self.lambda_client = session.client("lambda", region_name=region)
        self.apigw = session.client("apigateway", region_name=region)
        self.agentcore_control = session.client("bedrock-agentcore-control", region_name=region)
        self.sts = session.client("sts", region_name=region)

        self.account_id = self.sts.get_caller_identity()["Account"]

        self.role_name = f"{team_id}-lambda-execution-role"
        self.function_name = f"{team_id}-orchestrator-handler"
        self.api_name = f"{team_id}-orchestrator-api"

        logger.info(f"Team: {team_id} | Region: {region} | Account: {self.account_id}")

    # ------------------------------------------------------------------
    # Step 1: IAM role
    # ------------------------------------------------------------------
    def ensure_role(self) -> str:
        logger.info(f"--- Step 1: IAM role {self.role_name} ---")
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}
            ],
        }
        try:
            response = self.iam.create_role(
                RoleName=self.role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Lambda execution role for {self.team_id} orchestrator API",
            )
            role_arn = response["Role"]["Arn"]
            logger.info(f"Created role {role_arn}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "EntityAlreadyExists":
                role_arn = self.iam.get_role(RoleName=self.role_name)["Role"]["Arn"]
                logger.info(f"Role already exists: {role_arn}")
            else:
                raise

        policies = {
            f"{self.team_id}-agentcore-invoke": {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:InvokeAgentRuntime",
                        "bedrock-agentcore:CreateEvent",
                        "bedrock-agentcore:RetrieveMemoryRecords",
                        "bedrock-agentcore:GetEvent",
                        "sts:GetCallerIdentity",
                    ],
                    "Resource": "*",
                }],
            },
            f"{self.team_id}-lambda-policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                        "Resource": "arn:aws:logs:*:*:*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"],
                        "Resource": f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{self.team_id}-conversation-memory",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject"],
                        "Resource": f"arn:aws:s3:::{self.team_id}-*/*",
                    },
                ],
            },
            f"{self.team_id}-s3-synthetic-data-access": {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:ListBucket"],
                    "Resource": [
                        f"arn:aws:s3:::{self.team_id}-synthetic-data",
                        f"arn:aws:s3:::{self.team_id}-synthetic-data/*",
                    ],
                }],
            },
        }
        for policy_name, policy_doc in policies.items():
            self.iam.put_role_policy(
                RoleName=self.role_name, PolicyName=policy_name, PolicyDocument=json.dumps(policy_doc)
            )
            logger.info(f"  Put inline policy {policy_name}")

        logger.info("Waiting 10s for IAM role propagation...")
        time.sleep(10)
        return role_arn

    # ------------------------------------------------------------------
    # Step 2: look up prerequisite IDs
    # ------------------------------------------------------------------
    def lookup_orchestrator_runtime_id(self) -> str:
        endpoints_file = PROJECT_ROOT / f"agent_endpoints.{self.team_id}.json"
        if not endpoints_file.exists():
            logger.error(f"❌ {endpoints_file} not found - run deploy_to_agentcore_boto3.py first")
            sys.exit(1)
        data = json.loads(endpoints_file.read_text())
        runtime_id = data["details"]["orchestrator"]["runtime_id"]
        logger.info(f"Orchestrator runtime ID: {runtime_id}")
        return runtime_id

    def lookup_memory_id(self) -> str:
        """Optional - AgentCore Memory is not part of the current setup. Returns
        '' if no matching memory resource exists instead of failing."""
        memory_name = f"{self.team_id}_eco_sentinel_memory"
        try:
            response = self.agentcore_control.list_memories()
        except ClientError as e:
            logger.info(f"AgentCore Memory lookup skipped ({e}); AGENTCORE_MEMORY_ID left blank")
            return ""
        for mem in response.get("memories", []):
            if mem.get("id", "").startswith(memory_name):
                logger.info(f"AgentCore Memory ID: {mem['id']}")
                return mem["id"]
        logger.info(f"No memory found matching '{memory_name}*' - AGENTCORE_MEMORY_ID left blank")
        return ""

    # ------------------------------------------------------------------
    # Step 3: package + deploy Lambda
    # ------------------------------------------------------------------
    def package_lambda_code(self) -> bytes:
        logger.info("--- Step 3: Packaging Lambda code ---")
        temp_dir = tempfile.mkdtemp()
        try:
            requirements_file = FUNCTIONS_DIR / "requirements.txt"
            pip_args = [sys.executable, "-m", "pip", "install", "-t", temp_dir]
            if requirements_file.exists():
                pip_args += ["-r", str(requirements_file)]
            logger.info("Installing dependencies (boto3, fastapi, mangum)...")
            subprocess.run(pip_args, capture_output=True, check=True)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for py_file in FUNCTIONS_DIR.glob("*.py"):
                    zf.write(py_file, py_file.name)
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, arcname)
            logger.info("Package ready", )
            return zip_buffer.getvalue()
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def deploy_lambda(self, role_arn: str, orchestrator_runtime_id: str, memory_id: str) -> str:
        zip_bytes = self.package_lambda_code()
        env_vars = {
            "ORCHESTRATOR_RUNTIME_ID": orchestrator_runtime_id,
            "AGENTCORE_MEMORY_ID": memory_id,
            "AWS_REGION_NAME": self.region,
            "LOG_LEVEL": "INFO",
        }
        try:
            self.lambda_client.get_function(FunctionName=self.function_name)
            logger.info(f"Function {self.function_name} exists - updating code + config")
            self.lambda_client.update_function_code(FunctionName=self.function_name, ZipFile=zip_bytes)
            waiter = self.lambda_client.get_waiter("function_updated")
            waiter.wait(FunctionName=self.function_name)
            self.lambda_client.update_function_configuration(
                FunctionName=self.function_name,
                Handler=LAMBDA_HANDLER,
                Role=role_arn,
                Timeout=300,
                MemorySize=512,
                Environment={"Variables": env_vars},
            )
            waiter.wait(FunctionName=self.function_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.info(f"Creating function {self.function_name}")
                self.lambda_client.create_function(
                    FunctionName=self.function_name,
                    Runtime=LAMBDA_RUNTIME,
                    Role=role_arn,
                    Handler=LAMBDA_HANDLER,
                    Code={"ZipFile": zip_bytes},
                    Timeout=300,
                    MemorySize=512,
                    Environment={"Variables": env_vars},
                    Description="AgentCore Orchestrator Lambda Handler",
                )
                waiter = self.lambda_client.get_waiter("function_active")
                waiter.wait(FunctionName=self.function_name)
            else:
                raise

        function_arn = self.lambda_client.get_function(FunctionName=self.function_name)["Configuration"]["FunctionArn"]
        logger.info(f"✓ Lambda ready: {function_arn}")
        return function_arn

    # ------------------------------------------------------------------
    # Step 4: REST API Gateway
    # ------------------------------------------------------------------
    def deploy_api_gateway(self, function_arn: str) -> dict:
        logger.info("--- Step 4: REST API Gateway ---")
        existing = self.apigw.get_rest_apis(limit=500)["items"]
        api = next((a for a in existing if a["name"] == self.api_name), None)
        if api:
            api_id = api["id"]
            logger.info(f"API {self.api_name} exists ({api_id})")
        else:
            api = self.apigw.create_rest_api(
                name=self.api_name,
                description="AgentCore Orchestrator API",
                endpointConfiguration={"types": ["REGIONAL"]},
            )
            api_id = api["id"]
            logger.info(f"Created API {api_id}")

        resources = self.apigw.get_resources(restApiId=api_id)["items"]
        root_id = next(r["id"] for r in resources if r["path"] == "/")
        proxy_resource = next((r for r in resources if r.get("pathPart") == "{proxy+}"), None)
        if not proxy_resource:
            proxy_resource = self.apigw.create_resource(
                restApiId=api_id, parentId=root_id, pathPart="{proxy+}"
            )
        proxy_id = proxy_resource["id"]

        lambda_uri = (
            f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{function_arn}/invocations"
        )
        for resource_id in (root_id, proxy_id):
            try:
                self.apigw.put_method(
                    restApiId=api_id, resourceId=resource_id, httpMethod="ANY",
                    authorizationType="NONE",
                )
            except ClientError as e:
                if e.response["Error"]["Code"] != "ConflictException":
                    raise
            self.apigw.put_integration(
                restApiId=api_id, resourceId=resource_id, httpMethod="ANY",
                type="AWS_PROXY", integrationHttpMethod="POST", uri=lambda_uri,
                timeoutInMillis=29000,
            )

        self.apigw.create_deployment(restApiId=api_id, stageName=STAGE_NAME)
        logger.info(f"✓ Deployed stage '{STAGE_NAME}'")

        source_arn = f"arn:aws:execute-api:{self.region}:{self.account_id}:{api_id}/*/*/*"
        try:
            self.lambda_client.add_permission(
                FunctionName=self.function_name,
                StatementId=f"{self.api_name}-invoke",
                Action="lambda:InvokeFunction",
                Principal="apigateway.amazonaws.com",
                SourceArn=source_arn,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceConflictException":
                raise
            logger.info("Invoke permission already granted")

        domain = f"{api_id}.execute-api.{self.region}.amazonaws.com"
        return {
            "api_id": api_id,
            "domain": domain,
            "stage": STAGE_NAME,
            "invoke_url": f"https://{domain}/{STAGE_NAME}",
        }

    def run(self):
        role_arn = self.ensure_role()
        orchestrator_runtime_id = self.lookup_orchestrator_runtime_id()
        memory_id = self.lookup_memory_id()
        function_arn = self.deploy_lambda(role_arn, orchestrator_runtime_id, memory_id)
        api_info = self.deploy_api_gateway(function_arn)

        output = {
            "team_id": self.team_id,
            "region": self.region,
            "function_name": self.function_name,
            "function_arn": function_arn,
            **api_info,
        }
        out_file = PROJECT_ROOT / f"api_gateway_endpoints.{self.team_id}.json"
        out_file.write_text(json.dumps(output, indent=2))

        logger.info("=" * 60)
        logger.info(f"✓ Done. Invoke URL: {api_info['invoke_url']}")
        logger.info(f"  For deploy_cloudfront.py, set:")
        logger.info(f"    API_GATEWAY_DOMAIN={api_info['domain']}")
        logger.info(f"    API_GATEWAY_STAGE_PATH=/{STAGE_NAME}")
        logger.info(f"  Written to {out_file}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--team-id", required=True, help="Team namespace, e.g. team02")
    parser.add_argument("--region", default="eu-central-1")
    parser.add_argument("--profile", default="StandardAccess-450410489798")
    args = parser.parse_args()

    deployer = LambdaApiGatewayDeployer(team_id=args.team_id, region=args.region, profile=args.profile)
    deployer.run()


if __name__ == "__main__":
    main()
