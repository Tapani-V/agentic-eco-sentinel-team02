#!/usr/bin/env python3
"""
Manual Lambda deployment bypassing SAM S3 upload issues
"""

import os
import sys
import json
import zipfile
import subprocess
import boto3
from pathlib import Path
from botocore.exceptions import ClientError

# Change to project root
os.chdir(os.path.dirname(__file__) + '/..')

# Load environment
def load_env_file(env_file='.agentcore.env'):
    env_vars = {}
    if not os.path.exists(env_file):
        print(f"⚠️  Environment file not found: {env_file}")
        return env_vars
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars

# Create ZIP of Lambda function
def create_lambda_zip():
    zip_path = '/tmp/lambda_function.zip'
    build_dir = 'functions/.aws-sam/build/OrchestratorLambda'
    
    print(f"📦 Creating Lambda ZIP from {build_dir}...")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(build_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, build_dir)
                zf.write(file_path, arcname)
    
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"✅ Lambda ZIP created: {zip_path} ({size_mb:.2f} MB)")
    return zip_path

# Upload to S3
def upload_to_s3(profile, region, zip_path):
    bucket = f"agentcore-orchestrator-lambda-artifacts-{boto3.client('sts').get_caller_identity()['Account']}"
    key = 'lambda_function.zip'
    
    try:
        session = boto3.Session(profile_name=profile)
        s3 = session.client('s3', region_name=region)
        
        print(f"📤 Uploading to S3: s3://{bucket}/{key}...")
        s3.upload_file(zip_path, bucket, key)
        print(f"✅ Upload successful!")
        
        return f"s3://{bucket}/{key}"
    except ClientError as e:
        print(f"❌ Upload failed: {e}")
        return None

# Deploy CloudFormation stack
def deploy_stack(profile, region, s3_url, env_vars):
    print(f"📋 Deploying CloudFormation stack...")
    
    # Read template
    with open('functions/template.yaml', 'r') as f:
        template_body = f.read()
    
    # Prepare parameters
    params = [
        {'ParameterKey': 'OrchestratorEndpoint', 'ParameterValue': 'https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/orchestrator_runtime-6UF3HDGyvL'},
        {'ParameterKey': 'CognitoClientId', 'ParameterValue': env_vars.get('COGNITO_APP_CLIENT_ID', '')},
        {'ParameterKey': 'CognitoClientSecret', 'ParameterValue': env_vars.get('COGNITO_APP_CLIENT_SECRET', '')},
        {'ParameterKey': 'CognitoTokenEndpoint', 'ParameterValue': env_vars.get('COGNITO_TOKEN_ENDPOINT', '')},
        {'ParameterKey': 'CognitoScope', 'ParameterValue': env_vars.get('COGNITO_SCOPE', 'agentcore/invoke')},
        {'ParameterKey': 'GatewayUrl', 'ParameterValue': env_vars.get('GATEWAY_URL', '')},
    ]
    
    try:
        session = boto3.Session(profile_name=profile)
        cf = session.client('cloudformation', region_name=region)
        
        # Try to create or update stack
        stack_name = 'agentcore-orchestrator-lambda'
        
        try:
            cf.describe_stacks(StackName=stack_name)
            # Stack exists, update it
            print(f"🔄 Updating existing stack: {stack_name}")
            cf.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=params,
                Capabilities=['CAPABILITY_IAM', 'CAPABILITY_AUTO_EXPAND']
            )
        except cf.exceptions.ClientError as e:
            if 'does not exist' in str(e):
                # Stack doesn't exist, create it
                print(f"✨ Creating new stack: {stack_name}")
                cf.create_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=params,
                    Capabilities=['CAPABILITY_IAM', 'CAPABILITY_AUTO_EXPAND']
                )
            else:
                raise
        
        print(f"✅ Stack deployment initiated!")
        return True
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        return False

# Main
if __name__ == '__main__':
    profile = sys.argv[1] if len(sys.argv) > 1 else 'StandardAccess-450410489798'
    region = sys.argv[2] if len(sys.argv) > 2 else 'us-east-1'
    
    print(f"🚀 Lambda Manual Deployment")
    print(f"   Profile: {profile}")
    print(f"   Region: {region}\n")
    
    # Load environment
    env_vars = load_env_file()
    if not env_vars:
        print("❌ Failed to load environment variables")
        sys.exit(1)
    
    # Create ZIP
    zip_path = create_lambda_zip()
    
    # Upload to S3
    s3_url = upload_to_s3(profile, region, zip_path)
    if not s3_url:
        print("❌ Failed to upload to S3")
        sys.exit(1)
    
    # Deploy
    if deploy_stack(profile, region, s3_url, env_vars):
        print("\n✨ Deployment successful! Check AWS Console for stack status.")
    else:
        print("\n❌ Deployment failed!")
        sys.exit(1)
