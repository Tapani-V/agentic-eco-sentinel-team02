#!/usr/bin/env python3
"""
Deploy React Dashboard to AWS CloudFront + S3

This script:
1. Creates/updates the CloudFormation stack (S3 bucket + CloudFront distribution)
2. Builds the React frontend with the cloudfront mode (base = '/')
3. Syncs the built assets to the S3 bucket with correct content types
4. Creates a CloudFront cache invalidation
5. Prints the CloudFront URL on success

Usage:
    python scripts/deploy_cloudfront.py

Requirements:
    - boto3 installed
    - AWS credentials configured (via profile, env vars, or instance role)
    - Node.js and npm available on PATH
"""

import os
import sys
import time
import subprocess
import mimetypes
from pathlib import Path
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

# --- Configuration -----------------------------------------------------------

RESOURCE_PREFIX = os.getenv("RESOURCE_PREFIX", "team1-")
STACK_NAME = f"{RESOURCE_PREFIX}dashboard"
TEMPLATE_PATH = "infra/cloudfront-dashboard.yaml"
FRONTEND_DIR = "frontend"

# Project root is one level up from scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Logging -----------------------------------------------------------------

GREEN = "\033[92m"
BLUE = "\033[94m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def log(msg: str, level: str = "info") -> None:
    """Print a timestamped log message."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if level == "success":
        print(f"{GREEN}[✓ {ts}]{RESET} {msg}")
    elif level == "error":
        print(f"{RED}[✗ {ts}]{RESET} {msg}")
    elif level == "warn":
        print(f"{YELLOW}[⚠ {ts}]{RESET} {msg}")
    else:
        print(f"{BLUE}[INFO {ts}]{RESET} {msg}")


# --- Content-Type Mapping ----------------------------------------------------

CONTENT_TYPE_MAP = {
    ".html": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json",
    ".txt": "text/plain",
    ".xml": "application/xml",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def guess_content_type(file_path: Path) -> str:
    """Return the content type for a file based on its extension."""
    ext = file_path.suffix.lower()
    if ext in CONTENT_TYPE_MAP:
        return CONTENT_TYPE_MAP[ext]
    # Fallback to mimetypes module
    mime, _ = mimetypes.guess_type(str(file_path))
    return mime or "application/octet-stream"


# --- CloudFormation ----------------------------------------------------------

def deploy_stack(cf_client) -> dict:
    """Create or update the CloudFormation stack. Returns stack outputs."""
    template_path = PROJECT_ROOT / TEMPLATE_PATH
    if not template_path.exists():
        log(f"CloudFormation template not found: {template_path}", "error")
        sys.exit(1)

    template_body = template_path.read_text()

    # Check if stack already exists
    stack_exists = False
    try:
        cf_client.describe_stacks(StackName=STACK_NAME)
        stack_exists = True
    except ClientError as e:
        if "does not exist" not in str(e):
            raise

    if stack_exists:
        log(f"Stack '{STACK_NAME}' exists — updating...")
        try:
            cf_client.update_stack(
                StackName=STACK_NAME,
                TemplateBody=template_body,
                Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
            )
            log("Waiting for stack update to complete...")
            waiter = cf_client.get_waiter("stack_update_complete")
            waiter.wait(
                StackName=STACK_NAME,
                WaiterConfig={"Delay": 10, "MaxAttempts": 60},
            )
            log("Stack update complete.", "success")
        except ClientError as e:
            error_msg = str(e)
            if "No updates are to be performed" in error_msg:
                log("No stack changes detected — continuing with current resources.", "warn")
            else:
                log(f"Stack update failed: {error_msg}", "error")
                sys.exit(1)
    else:
        log(f"Stack '{STACK_NAME}' does not exist — creating...")
        cf_client.create_stack(
            StackName=STACK_NAME,
            TemplateBody=template_body,
            Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
        )
        log("Waiting for stack creation to complete...")
        waiter = cf_client.get_waiter("stack_create_complete")
        waiter.wait(
            StackName=STACK_NAME,
            WaiterConfig={"Delay": 10, "MaxAttempts": 120},
        )
        log("Stack creation complete.", "success")

    # Read stack outputs
    response = cf_client.describe_stacks(StackName=STACK_NAME)
    outputs = {}
    for output in response["Stacks"][0].get("Outputs", []):
        outputs[output["OutputKey"]] = output["OutputValue"]

    required_outputs = ["BucketName", "DistributionId", "DistributionDomainName"]
    for key in required_outputs:
        if key not in outputs:
            log(f"Missing expected stack output: {key}", "error")
            sys.exit(1)

    log(f"Bucket: {outputs['BucketName']}")
    log(f"Distribution: {outputs['DistributionId']}")
    log(f"Domain: {outputs['DistributionDomainName']}")

    return outputs


# --- Frontend Build ----------------------------------------------------------

def build_frontend() -> Path:
    """Install dependencies and build the frontend for CloudFront deployment."""
    frontend_dir = PROJECT_ROOT / FRONTEND_DIR

    if not frontend_dir.exists():
        log(f"Frontend directory not found: {frontend_dir}", "error")
        sys.exit(1)

    log("Installing frontend dependencies (npm ci)...")
    result = subprocess.run(
        ["npm", "ci"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log("npm ci failed:", "error")
        print(result.stderr)
        sys.exit(1)
    log("Dependencies installed.", "success")

    log("Building frontend for CloudFront (npm run build:cloudfront)...")
    result = subprocess.run(
        ["npm", "run", "build:cloudfront"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log("Frontend build failed:", "error")
        print(result.stderr)
        sys.exit(1)
    log("Frontend build complete.", "success")

    dist_dir = frontend_dir / "dist"
    if not dist_dir.exists():
        log(f"Build output directory not found: {dist_dir}", "error")
        sys.exit(1)

    return dist_dir


# --- S3 Sync ----------------------------------------------------------------

def sync_to_s3(s3_client, dist_dir: Path, bucket_name: str) -> None:
    """Upload built assets to S3 with correct content types, delete orphaned objects."""
    log(f"Syncing {dist_dir} to s3://{bucket_name}/...")

    # Collect local files (relative paths)
    local_files = {}
    for file_path in dist_dir.rglob("*"):
        if file_path.is_file():
            rel_path = file_path.relative_to(dist_dir)
            # Use forward slashes for S3 keys
            s3_key = str(rel_path).replace(os.sep, "/")
            local_files[s3_key] = file_path

    # Upload each file
    uploaded = 0
    for s3_key, file_path in local_files.items():
        content_type = guess_content_type(file_path)
        s3_client.upload_file(
            str(file_path),
            bucket_name,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        uploaded += 1

    log(f"Uploaded {uploaded} files.", "success")

    # Delete orphaned objects in the bucket that are not in the local build
    log("Checking for orphaned objects...")
    orphaned = 0
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get("Contents", []):
            if obj["Key"] not in local_files:
                s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
                orphaned += 1

    if orphaned:
        log(f"Deleted {orphaned} orphaned object(s).", "warn")
    else:
        log("No orphaned objects found.")


# --- CloudFront Invalidation ------------------------------------------------

def invalidate_cache(cf_client_cloudfront, distribution_id: str) -> None:
    """Create a CloudFront cache invalidation for all paths."""
    log(f"Creating cache invalidation for distribution {distribution_id}...")

    caller_ref = f"deploy-{int(time.time())}"
    cf_client_cloudfront.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            "Paths": {
                "Quantity": 1,
                "Items": ["/*"],
            },
            "CallerReference": caller_ref,
        },
    )
    log("Cache invalidation created (propagation may take a few minutes).", "success")


# --- Bucket Policy (post-stack) ----------------------------------------------

def apply_cloudfront_bucket_policy(s3_client, session, bucket_name: str, distribution_id: str) -> None:
    """Apply CloudFront OAC bucket policy, merging with any existing org policy."""
    import json

    account_id = session.client("sts").get_caller_identity()["Account"]

    # The statement we need for CloudFront OAC
    oac_statement = {
        "Sid": "AllowCloudFrontOAC",
        "Effect": "Allow",
        "Principal": {"Service": "cloudfront.amazonaws.com"},
        "Action": "s3:GetObject",
        "Resource": f"arn:aws:s3:::{bucket_name}/*",
        "Condition": {
            "StringEquals": {
                "AWS:SourceArn": f"arn:aws:cloudfront::{account_id}:distribution/{distribution_id}"
            }
        },
    }

    # Get existing policy (org may have auto-applied one)
    try:
        existing = json.loads(s3_client.get_bucket_policy(Bucket=bucket_name)["Policy"])
        log(f"Existing policy found with {len(existing['Statement'])} statement(s) — merging.")
    except Exception:
        existing = {"Version": "2012-10-17", "Statement": []}

    # Remove any old OAC statement, then add fresh one
    existing["Statement"] = [
        s for s in existing["Statement"] if s.get("Sid") != "AllowCloudFrontOAC"
    ]
    existing["Statement"].append(oac_statement)

    s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(existing))
    log("CloudFront OAC bucket policy applied.", "success")


# --- Main --------------------------------------------------------------------

def main():
    """Run the full deployment pipeline."""
    log("=" * 60)
    log("Eco-Sentinel Dashboard — CloudFront Deployment")
    log("=" * 60)

    # Initialize AWS clients
    session = boto3.Session(region_name=os.getenv("AWS_REGION", "eu-central-1"))
    cf_client = session.client("cloudformation")
    s3_client = session.client("s3")
    cloudfront_client = session.client("cloudfront")

    # Step 1: Deploy/update CloudFormation stack
    log("\n--- Step 1: CloudFormation Stack ---")
    outputs = deploy_stack(cf_client)

    bucket_name = outputs["BucketName"]
    distribution_id = outputs["DistributionId"]
    domain_name = outputs["DistributionDomainName"]

    # Step 1b: Apply CloudFront OAC bucket policy (merge with org auto-policy)
    log("\n--- Step 1b: Apply Bucket Policy for CloudFront OAC ---")
    apply_cloudfront_bucket_policy(s3_client, session, bucket_name, distribution_id)

    # Step 2: Build the frontend
    log("\n--- Step 2: Build Frontend ---")
    dist_dir = build_frontend()

    # Step 3: Sync assets to S3
    log("\n--- Step 3: Sync to S3 ---")
    sync_to_s3(s3_client, dist_dir, bucket_name)

    # Step 4: Invalidate CloudFront cache
    log("\n--- Step 4: Invalidate Cache ---")
    invalidate_cache(cloudfront_client, distribution_id)

    # Done
    log("\n" + "=" * 60)
    log(f"Deployment complete!", "success")
    log(f"Dashboard URL: https://{domain_name}", "success")
    log("=" * 60)


if __name__ == "__main__":
    main()
