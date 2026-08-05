#!/usr/bin/env python3
"""
Deploy Lambda + API Gateway using boto3 (no SAM/CloudFormation)

Simple, direct approach:
1. Package Lambda handler code
2. Create Lambda function
3. Create API Gateway REST API
4. Wire POST /orchestrate endpoint
5. Output API endpoint URL
"""

import os
import sys
import json
import zipfile
import io
import time
import boto3
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Colors for output
GREEN = '\033[92m'
BLUE = '\033[94m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'


def log(msg, level='info'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if level == 'success':
        print(f"{GREEN}[✓ {ts}]{RESET} {msg}")
    elif level == 'error':
        print(f"{RED}[✗ {ts}]{RESET} {msg}")
    else:
        print(f"{BLUE}[INFO {ts}]{RESET} {msg}")


def load_env_file(env_file):
    """Load environment variables"""
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def package_lambda_code():
    """Create ZIP package with handler code AND dependencies"""
    log("Packaging Lambda handler code with dependencies...")
    
    # Create temporary directory for dependencies
    temp_dir = tempfile.mkdtemp()
    try:
        # Install dependencies into temp directory
        requirements_file = 'functions/requirements.txt'
        if os.path.exists(requirements_file):
            log(f"Installing dependencies from {requirements_file}...")
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', requirements_file, '-t', temp_dir],
                capture_output=True,
                check=True
            )
            log("Dependencies installed", 'success')
        
        # Create in-memory ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add handler file
            handler_path = 'functions/lambda_orchestrator_handler.py'
            if os.path.exists(handler_path):
                with open(handler_path, 'r') as f:
                    zf.writestr('lambda_orchestrator_handler.py', f.read())
                log(f"Added {handler_path}")
            else:
                log(f"Handler file not found: {handler_path}", 'error')
                return None
            
            # Add all dependencies from temp directory
            log(f"Adding dependencies from {temp_dir}...")
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    # Skip .dist-info and .egg-info directories (not needed in Lambda)
                    if '.dist-info' not in arcname and '.egg-info' not in arcname:
                        zf.write(file_path, arcname)
        
        zip_buffer.seek(0)
        log("Lambda package ready (with dependencies)", 'success')
        return zip_buffer.getvalue()
        
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def create_lambda_function(lambda_client, account_id, env_vars, zip_content):
    """Create or update Lambda function"""
    function_name = f"orchestrator-handler-{account_id}"
    
    log(f"Creating/updating Lambda function: {function_name}...")
    
    # Use existing IAM role for Lambda
    iam_client = boto3.client('iam')
    
    # Try to find existing Lambda execution role
    role_arn = None
    role_names = ['agentic-ai-lambda-execution-role', 'AgentCoreLambdaExecutionRole', 'agentcore-sample-lambdagateway-role']
    
    for role_name in role_names:
        try:
            role_response = iam_client.get_role(RoleName=role_name)
            role_arn = role_response['Role']['Arn']
            log(f"Using existing IAM role: {role_name}", 'success')
            break
        except iam_client.exceptions.NoSuchEntityException:
            continue
    
    if not role_arn:
        log(f"Error: No existing Lambda execution role found", 'error')
        log(f"Tried: {', '.join(role_names)}", 'error')
        raise Exception("Cannot find Lambda execution role")
    
    # Prepare environment variables
    lambda_env = {
        'ORCHESTRATOR_ENDPOINT': env_vars.get('ORCHESTRATOR_ENDPOINT', env_vars.get('GATEWAY_URL', '')),
        'COGNITO_APP_CLIENT_ID': env_vars.get('COGNITO_APP_CLIENT_ID', ''),
        'COGNITO_APP_CLIENT_SECRET': env_vars.get('COGNITO_APP_CLIENT_SECRET', ''),
        'COGNITO_TOKEN_ENDPOINT': env_vars.get('COGNITO_TOKEN_ENDPOINT', ''),
        'COGNITO_SCOPE': env_vars.get('COGNITO_SCOPE', 'agentcore/invoke'),
        'GATEWAY_URL': env_vars.get('GATEWAY_URL', ''),
        'LOG_LEVEL': 'INFO'
    }
    
    try:
        # Try to get existing function
        lambda_client.get_function(FunctionName=function_name)
        log(f"Updating existing Lambda function...")
        
        # Retry logic for in-progress updates
        max_retries = 5
        code_updated = False
        config_updated = False
        
        for attempt in range(max_retries):
            try:
                if not code_updated:
                    lambda_client.update_function_code(
                        FunctionName=function_name,
                        ZipFile=zip_content
                    )
                    code_updated = True
                    log("Code updated", 'success')
                
                if not config_updated:
                    lambda_client.update_function_configuration(
                        FunctionName=function_name,
                        Environment={'Variables': lambda_env},
                        Timeout=120,
                        MemorySize=512
                    )
                    config_updated = True
                    log("Configuration updated", 'success')
                
                if code_updated and config_updated:
                    break
                    
            except lambda_client.exceptions.ResourceConflictException:
                if attempt < max_retries - 1:
                    log(f"Lambda update in progress, waiting... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(10)
                else:
                    # If we updated code successfully, that's enough - skip config update
                    if code_updated:
                        log("Code update succeeded, skipping configuration (Lambda still updating)")
                        break
                    else:
                        raise
        
    except lambda_client.exceptions.ResourceNotFoundException:
        log(f"Creating new Lambda function...")
        
        lambda_client.create_function(
            FunctionName=function_name,
            Runtime='python3.10',
            Role=role_arn,
            Handler='lambda_orchestrator_handler.lambda_handler',
            Code={'ZipFile': zip_content},
            Timeout=120,
            MemorySize=512,
            Environment={'Variables': lambda_env},
            Description='AgentCore Orchestrator Lambda Handler'
        )
    
    log(f"Lambda function ready: {function_name}", 'success')
    return function_name


def create_api_gateway(apigw_client, lambda_client, function_name):
    """Create API Gateway and wire to Lambda"""
    log("Setting up API Gateway...")
    
    api_name = 'agentcore-orchestrator-api'
    
    # Check if API already exists
    apis = apigw_client.get_rest_apis()
    api_id = None
    for api in apis['items']:
        if api['name'] == api_name:
            api_id = api['id']
            log(f"Using existing API Gateway: {api_id}", 'success')
            break
    
    if not api_id:
        log("Creating new API Gateway...")
        api_response = apigw_client.create_rest_api(
            name=api_name,
            description='AgentCore Orchestrator API',
            endpointConfiguration={'types': ['REGIONAL']}
        )
        api_id = api_response['id']
        log(f"API Gateway created: {api_id}", 'success')
    
    # Get root resource
    resources = apigw_client.get_resources(restApiId=api_id)
    root_id = [r for r in resources['items'] if r['path'] == '/'][0]['id']
    
    # Create /orchestrate resource
    orchestrate_resource = None
    for resource in resources['items']:
        if resource.get('pathPart') == 'orchestrate':
            orchestrate_resource = resource
            log(f"Using existing /orchestrate resource")
            break
    
    if not orchestrate_resource:
        log("Creating /orchestrate resource...")
        orchestrate_response = apigw_client.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart='orchestrate'
        )
        orchestrate_resource = orchestrate_response
    
    resource_id = orchestrate_resource['id']
    
    # Add POST method
    log("Adding POST method...")
    try:
        apigw_client.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='POST',
            authorizationType='NONE'
        )
    except:
        pass  # Method might already exist
    
    # Add OPTIONS method for CORS
    log("Adding OPTIONS method for CORS...")
    try:
        apigw_client.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            authorizationType='NONE'
        )
    except apigw_client.exceptions.ConflictException:
        log("OPTIONS method already exists")
    
    # Wire Lambda to POST method
    log("Wiring Lambda to POST method...")
    account_id = boto3.client('sts').get_caller_identity()['Account']
    lambda_arn = f"arn:aws:lambda:us-east-1:{account_id}:function:{function_name}"
    
    try:
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='POST',
            type='AWS_PROXY',
            integrationHttpMethod='POST',
            uri=f"arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/{lambda_arn}/invocations"
        )
        log("POST method wired to Lambda", 'success')
    except apigw_client.exceptions.ConflictException:
        log("POST integration already exists")
    
    # Add OPTIONS integration (MOCK for CORS preflight)
    log("Adding OPTIONS integration...")
    try:
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            type='MOCK'
        )
        log("OPTIONS integration added", 'success')
    except apigw_client.exceptions.ConflictException:
        log("OPTIONS integration already exists")
    
    # Add CORS responses
    log("Adding CORS headers...")
    for method in ['POST', 'OPTIONS']:
        try:
            apigw_client.put_method_response(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod=method,
                statusCode='200',
                responseParameters={
                    'method.response.header.Access-Control-Allow-Headers': False,
                    'method.response.header.Access-Control-Allow-Methods': False,
                    'method.response.header.Access-Control-Allow-Origin': False
                }
            )
        except apigw_client.exceptions.ConflictException:
            pass  # Response already exists
        
        try:
            apigw_client.put_integration_response(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod=method,
                statusCode='200',
                responseParameters={
                    'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key'",
                    'method.response.header.Access-Control-Allow-Methods': "'POST,OPTIONS'",
                    'method.response.header.Access-Control-Allow-Origin': "'*'"
                }
            )
        except apigw_client.exceptions.ConflictException:
            pass  # Response already exists
    
    log("CORS headers configured", 'success')
    
    # Grant Lambda permission for API Gateway
    log("Granting API Gateway permission to invoke Lambda...")
    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId=f"AllowAPIGateway-{api_id}",
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn=f"arn:aws:execute-api:us-east-1:{account_id}:{api_id}/*"
        )
        log("Lambda permission granted", 'success')
    except lambda_client.exceptions.ResourceConflictException:
        log("Lambda permission already exists")
    
    # Deploy API to 'prod' stage (makes it publicly accessible)
    log("Deploying API to 'prod' stage (this makes the endpoint accessible)...")
    try:
        deployment = apigw_client.create_deployment(
            restApiId=api_id,
            stageName='prod',
            stageDescription='Production stage'
        )
        log(f"API deployed to prod stage: {deployment['id']}", 'success')
    except apigw_client.exceptions.BadRequestException as e:
        error_msg = str(e)
        if "No integration defined" in error_msg:
            log("ERROR: Missing integration - check POST/OPTIONS methods have integrations", 'error')
            raise
        elif "Stage already exists" in error_msg or "already exists" in error_msg.lower():
            log("Prod stage already exists, deployment skipped")
        else:
            log(f"Deployment error: {e}", 'error')
            raise
    except Exception as e:
        log(f"Unexpected deployment error: {e}", 'error')
        raise
    
    endpoint = f"https://{api_id}.execute-api.us-east-1.amazonaws.com/prod/orchestrate"
    log(f"API Gateway ready: {endpoint}", 'success')
    
    return endpoint


def main():
    print(f"\n{BOLD}=== Deploy Lambda + API Gateway (boto3){RESET}\n")
    
    # Load environment
    env_vars = load_env_file('.agentcore.env')
    if not env_vars:
        log("Error: .agentcore.env not found", 'error')
        sys.exit(1)
    
    try:
        # Get AWS credentials
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity()['Account']
        log(f"AWS Account: {account_id}", 'success')
        
        # Create clients
        lambda_client = boto3.client('lambda')
        apigw_client = boto3.client('apigateway')
        
        # Deploy steps
        zip_content = package_lambda_code()
        if not zip_content:
            sys.exit(1)
        
        function_name = create_lambda_function(lambda_client, account_id, env_vars, zip_content)
        endpoint = create_api_gateway(apigw_client, lambda_client, function_name)
        
        # Summary
        print(f"\n{BOLD}=== Deployment Complete ==={RESET}\n")
        print(f"Lambda Function: {function_name}")
        print(f"API Endpoint:    {endpoint}")
        print(f"\n{BLUE}Test with curl:{RESET}")
        print(f"curl -X POST {endpoint} \\")
        print(f"  -H 'Content-Type: application/json' \\")
        print(f"  -d '{{\"device_id\":\"motor-004\",\"equipment_type\":\"MOTOR\",\"current_reading\":{{}}}}'\n")
        
    except Exception as e:
        log(f"Deployment failed: {e}", 'error')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
