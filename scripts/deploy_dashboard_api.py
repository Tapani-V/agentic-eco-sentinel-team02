#!/usr/bin/env python3
"""
Deploy Dashboard_Service as Lambda + HTTP API Gateway.

This script:
1. Packages the FastAPI dashboard app + dependencies into a Lambda zip
2. Uploads the zip to an S3 code bucket
3. Creates/updates the CloudFormation stack (Lambda + HTTP API GW)
4. Updates the CloudFront distribution to point /api/* to the new API
5. Prints the API endpoint URL

Usage:
    python scripts/deploy_dashboard_api.py

Requirements:
    - boto3 installed
    - pip available (for installing Lambda dependencies)
    - AWS credentials configured
"""

import os
import sys
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

# --- Configuration -----------------------------------------------------------

RESOURCE_PREFIX = os.getenv("RESOURCE_PREFIX", "team1-")
STACK_NAME = f"{RESOURCE_PREFIX}dashboard-api"
TEMPLATE_PATH = "infra/dashboard-api.yaml"
CLOUDFRONT_STACK_NAME = f"{RESOURCE_PREFIX}dashboard"

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Logging -----------------------------------------------------------------

GREEN = "\033[92m"
BLUE = "\033[94m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def log(msg: str, level: str = "info") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    if level == "success":
        print(f"{GREEN}[✓ {ts}]{RESET} {msg}")
    elif level == "error":
        print(f"{RED}[✗ {ts}]{RESET} {msg}")
    elif level == "warn":
        print(f"{YELLOW}[⚠ {ts}]{RESET} {msg}")
    else:
        print(f"{BLUE}[{ts}]{RESET} {msg}")


# --- Package Lambda ----------------------------------------------------------

LAMBDA_DEPENDENCIES = [
    "fastapi==0.104.1",
    "uvicorn==0.24.0",
    "httpx==0.25.0",
    "pydantic==2.4.2",
    "pydantic-settings==2.1.0",
    "python-dotenv==1.0.0",
    "mangum==0.17.0",
    "jinja2==3.1.2",
    "starlette==0.27.0",
]


def package_lambda() -> Path:
    """Package the dashboard code + dependencies into a Lambda zip."""
    log("Packaging Lambda function...")

    build_dir = PROJECT_ROOT / "build" / "lambda"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)

    # Install dependencies into the build dir
    log("Installing Python dependencies...")
    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--target", str(build_dir),
            "--platform", "manylinux2014_x86_64",
            "--implementation", "cp",
            "--python-version", "3.11",
            "--only-binary=:all:",
            "--upgrade",
        ] + LAMBDA_DEPENDENCIES,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Fallback: try without platform constraints (works for pure Python packages)
        log("Platform-specific install failed, trying without platform flag...", "warn")
        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--target", str(build_dir),
                "--upgrade",
            ] + LAMBDA_DEPENDENCIES,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log(f"pip install failed:\n{result.stderr}", "error")
            sys.exit(1)

    log("Dependencies installed.", "success")

    # Copy the dashboard source code preserving package structure
    src_dir = PROJECT_ROOT / "src"
    dest_src = build_dir / "src"
    dest_src.mkdir(exist_ok=True)

    # Create src/__init__.py
    (dest_src / "__init__.py").write_text("")

    # Copy src/dashboard/
    dashboard_src = src_dir / "dashboard"
    dashboard_dest = dest_src / "dashboard"
    shutil.copytree(
        dashboard_src,
        dashboard_dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "static"),
    )

    # Copy src/memory/ (AgentCore Memory integration)
    memory_src = src_dir / "memory"
    if memory_src.exists():
        memory_dest = dest_src / "memory"
        shutil.copytree(
            memory_src,
            memory_dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        log("Memory module copied.", "success")

    # Copy src/graph/ (workflow with memory integration)
    graph_src = src_dir / "graph"
    if graph_src.exists():
        graph_dest = dest_src / "graph"
        shutil.copytree(
            graph_src,
            graph_dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        log("Graph module copied.", "success")

    # Copy src/utils/ (device_loader, etc.)
    utils_src = src_dir / "utils"
    if utils_src.exists():
        utils_dest = dest_src / "utils"
        shutil.copytree(
            utils_src,
            utils_dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        log("Utils module copied.", "success")

    log("Dashboard source copied.", "success")

    # Create the zip
    zip_path = PROJECT_ROOT / "build" / "lambda-package.zip"
    log("Creating zip archive...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in build_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(build_dir)
                zf.write(file_path, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    log(f"Lambda package: {zip_path} ({size_mb:.1f} MB)", "success")

    return zip_path


# --- S3 Upload ---------------------------------------------------------------

def ensure_code_bucket(s3_client, bucket_name: str) -> None:
    """Create the code bucket if it doesn't exist."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError:
        log(f"Creating code bucket: {bucket_name}")
        region = s3_client.meta.region_name
        create_args = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_args["CreateBucketConfiguration"] = {
                "LocationConstraint": region
            }
        s3_client.create_bucket(**create_args)
        log(f"Bucket created.", "success")


def upload_package(s3_client, zip_path: Path, bucket_name: str) -> None:
    """Upload the Lambda package to S3."""
    log(f"Uploading package to s3://{bucket_name}/lambda-package.zip...")
    s3_client.upload_file(str(zip_path), bucket_name, "lambda-package.zip")
    log("Upload complete.", "success")


# --- CloudFormation ----------------------------------------------------------

def deploy_stack(cf_client, code_bucket: str) -> dict:
    """Create or update the dashboard API stack."""
    template_path = PROJECT_ROOT / TEMPLATE_PATH
    template_body = template_path.read_text()

    # Check if stack already exists
    stack_exists = False
    try:
        resp = cf_client.describe_stacks(StackName=STACK_NAME)
        status = resp["Stacks"][0]["StackStatus"]
        if status in ("ROLLBACK_COMPLETE", "ROLLBACK_FAILED"):
            log(f"Stack in {status} state — deleting before re-create...", "warn")
            cf_client.delete_stack(StackName=STACK_NAME)
            waiter = cf_client.get_waiter("stack_delete_complete")
            waiter.wait(StackName=STACK_NAME, WaiterConfig={"Delay": 10, "MaxAttempts": 60})
            stack_exists = False
        else:
            stack_exists = True
    except ClientError as e:
        if "does not exist" not in str(e):
            raise

    params = {
        "StackName": STACK_NAME,
        "TemplateBody": template_body,
        "Capabilities": ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
    }

    if stack_exists:
        log(f"Updating stack '{STACK_NAME}'...")
        try:
            cf_client.update_stack(**params)
            waiter = cf_client.get_waiter("stack_update_complete")
            waiter.wait(StackName=STACK_NAME, WaiterConfig={"Delay": 10, "MaxAttempts": 60})
            log("Stack update complete.", "success")
        except ClientError as e:
            if "No updates are to be performed" in str(e):
                log("No stack changes — continuing.", "warn")
            else:
                log(f"Stack update failed: {e}", "error")
                sys.exit(1)
    else:
        log(f"Creating stack '{STACK_NAME}'...")
        cf_client.create_stack(**params)
        waiter = cf_client.get_waiter("stack_create_complete")
        waiter.wait(StackName=STACK_NAME, WaiterConfig={"Delay": 10, "MaxAttempts": 120})
        log("Stack creation complete.", "success")

    # Get outputs
    response = cf_client.describe_stacks(StackName=STACK_NAME)
    outputs = {}
    for o in response["Stacks"][0].get("Outputs", []):
        outputs[o["OutputKey"]] = o["OutputValue"]

    return outputs


# --- Update Lambda Code ------------------------------------------------------

def update_lambda_code(lambda_client, function_name: str, bucket: str) -> None:
    """Update Lambda function code from S3."""
    log(f"Updating Lambda function code: {function_name}...")
    lambda_client.update_function_code(
        FunctionName=function_name,
        S3Bucket=bucket,
        S3Key="lambda-package.zip",
    )
    # Wait for update to complete
    waiter = lambda_client.get_waiter("function_updated_v2")
    waiter.wait(FunctionName=function_name)
    log("Lambda code updated.", "success")


# --- Update CloudFront -------------------------------------------------------

def update_cloudfront_origin(cf_client, cloudfront_client, api_endpoint: str) -> None:
    """Update the CloudFront distribution's API Gateway origin."""
    log("Updating CloudFront API origin...")

    # Get CloudFront distribution ID from the frontend stack
    try:
        resp = cf_client.describe_stacks(StackName=CLOUDFRONT_STACK_NAME)
        outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
        dist_id = outputs.get("DistributionId")
        if not dist_id:
            log("CloudFront stack not found — skipping origin update.", "warn")
            return
    except ClientError:
        log("CloudFront stack not found — skipping origin update.", "warn")
        return

    # Parse API endpoint domain (remove https:// prefix)
    api_domain = api_endpoint.replace("https://", "").rstrip("/")

    # Get current distribution config
    dist = cloudfront_client.get_distribution_config(Id=dist_id)
    config = dist["DistributionConfig"]
    etag = dist["ETag"]

    # Find and update the API Gateway origin
    updated = False
    for origin in config["Origins"]["Items"]:
        if origin["Id"] == "ApiGatewayOrigin":
            origin["DomainName"] = api_domain
            # HTTP API uses $default stage — no OriginPath needed
            origin["OriginPath"] = ""
            updated = True
            break

    if not updated:
        log("ApiGatewayOrigin not found in distribution — skipping.", "warn")
        return

    # Update the distribution
    cloudfront_client.update_distribution(
        Id=dist_id,
        DistributionConfig=config,
        IfMatch=etag,
    )
    log(f"CloudFront origin updated to: {api_domain}", "success")

    # Invalidate cache
    import time
    cloudfront_client.create_invalidation(
        DistributionId=dist_id,
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": ["/api/*"]},
            "CallerReference": f"api-deploy-{int(time.time())}",
        },
    )
    log("Cache invalidation created for /api/*.", "success")


# --- Main --------------------------------------------------------------------

def main():
    log("=" * 60)
    log("Eco-Sentinel — Dashboard API Deployment")
    log("=" * 60)

    session = boto3.Session(region_name=os.getenv("AWS_REGION", "eu-central-1"))
    region = session.region_name
    s3_client = session.client("s3")
    cf_client = session.client("cloudformation")
    lambda_client = session.client("lambda")
    cloudfront_client = session.client("cloudfront")

    code_bucket = f"{STACK_NAME}-code"

    # Step 1: Package Lambda
    log("\n--- Step 1: Package Lambda ---")
    zip_path = package_lambda()

    # Step 2: Upload to S3
    log("\n--- Step 2: Upload to S3 ---")
    ensure_code_bucket(s3_client, code_bucket)
    upload_package(s3_client, zip_path, code_bucket)

    # Step 3: Deploy/update CloudFormation stack
    log("\n--- Step 3: CloudFormation Stack ---")
    outputs = deploy_stack(cf_client, code_bucket)
    api_endpoint = outputs.get("ApiEndpoint", "")
    function_name = outputs.get("FunctionName", "")
    log(f"API Endpoint: {api_endpoint}")
    log(f"Function: {function_name}")

    # Step 4: Update Lambda code (in case stack already existed)
    log("\n--- Step 4: Update Lambda Code ---")
    if function_name:
        update_lambda_code(lambda_client, function_name, code_bucket)

    # Step 5: Update CloudFront origin
    log("\n--- Step 5: Update CloudFront ---")
    update_cloudfront_origin(cf_client, cloudfront_client, api_endpoint)

    # Done
    log("\n" + "=" * 60)
    log("Deployment complete!", "success")
    log(f"API Endpoint: {api_endpoint}", "success")
    log(f"Dashboard: https://d3q95ked62pwwr.cloudfront.net", "success")
    log("=" * 60)


if __name__ == "__main__":
    main()
