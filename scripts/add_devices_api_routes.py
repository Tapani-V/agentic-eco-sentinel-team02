#!/usr/bin/env python3
"""
Add GET routes for device listing/detail/summary/health to the existing
API Gateway, nested under /orchestrate (to match the dashboard's
OrchestratorClient, which builds URLs as f"{ORCHESTRATOR_URL}{endpoint}"
where ORCHESTRATOR_URL already ends in "/orchestrate").

Creates (all wired via AWS_PROXY to the existing orchestrator Lambda):
    GET /orchestrate/health
    GET /orchestrate/devices
    GET /orchestrate/devices/{device_id}
    GET /orchestrate/devices/{device_id}/summary

Usage:
    python scripts/add_devices_api_routes.py --profile StandardAccess-450410489798 --region us-east-1
"""

import argparse
import boto3


API_ID = 'mn6y8y0u26'
FUNCTION_NAME = 'orchestrator-handler-450410489798'
STAGE = 'prod'


def log(msg, level='info'):
    icon = {'info': 'ℹ️ ', 'success': '✅', 'error': '❌'}.get(level, '')
    print(f"{icon} {msg}")


def get_or_create_resource(apigw, api_id, parent_id, path_part):
    """Find a child resource by pathPart under parent_id, or create it."""
    resources = apigw.get_resources(restApiId=api_id, limit=500)['items']
    for r in resources:
        if r.get('parentId') == parent_id and r.get('pathPart') == path_part:
            log(f"Using existing resource: {r['path']}")
            return r
    resp = apigw.create_resource(restApiId=api_id, parentId=parent_id, pathPart=path_part)
    log(f"Created resource: {resp['path']}", 'success')
    return resp


def add_get_method_with_cors(apigw, api_id, resource_id, lambda_arn):
    """Add GET method (AWS_PROXY to lambda_arn) and OPTIONS method (CORS) to a resource."""
    # GET method
    try:
        apigw.put_method(restApiId=api_id, resourceId=resource_id, httpMethod='GET', authorizationType='NONE')
    except apigw.exceptions.ConflictException:
        pass

    try:
        apigw.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='GET',
            type='AWS_PROXY',
            integrationHttpMethod='POST',
            uri=f"arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/{lambda_arn}/invocations"
        )
        log("GET wired to Lambda", 'success')
    except apigw.exceptions.ConflictException:
        log("GET integration already exists")

    # OPTIONS method (CORS preflight)
    try:
        apigw.put_method(restApiId=api_id, resourceId=resource_id, httpMethod='OPTIONS', authorizationType='NONE')
    except apigw.exceptions.ConflictException:
        pass

    try:
        apigw.put_integration(restApiId=api_id, resourceId=resource_id, httpMethod='OPTIONS', type='MOCK',
                               requestTemplates={'application/json': '{"statusCode": 200}'})
    except apigw.exceptions.ConflictException:
        pass

    for method in ['GET', 'OPTIONS']:
        try:
            apigw.put_method_response(
                restApiId=api_id, resourceId=resource_id, httpMethod=method, statusCode='200',
                responseParameters={
                    'method.response.header.Access-Control-Allow-Headers': False,
                    'method.response.header.Access-Control-Allow-Methods': False,
                    'method.response.header.Access-Control-Allow-Origin': False
                }
            )
        except apigw.exceptions.ConflictException:
            pass

    try:
        apigw.put_integration_response(
            restApiId=api_id, resourceId=resource_id, httpMethod='OPTIONS', statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key'",
                'method.response.header.Access-Control-Allow-Methods': "'GET,OPTIONS'",
                'method.response.header.Access-Control-Allow-Origin': "'*'"
            }
        )
    except apigw.exceptions.ConflictException:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='StandardAccess-450410489798')
    parser.add_argument('--region', default='us-east-1')
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    apigw = session.client('apigateway')
    account_id = session.client('sts').get_caller_identity()['Account']
    lambda_arn = f"arn:aws:lambda:{args.region}:{account_id}:function:{FUNCTION_NAME}"

    resources = apigw.get_resources(restApiId=API_ID, limit=500)['items']
    orchestrate_resource = next(r for r in resources if r.get('pathPart') == 'orchestrate')
    orchestrate_id = orchestrate_resource['id']
    log(f"/orchestrate resource id: {orchestrate_id}")

    # /orchestrate/health
    health_resource = get_or_create_resource(apigw, API_ID, orchestrate_id, 'health')
    add_get_method_with_cors(apigw, API_ID, health_resource['id'], lambda_arn)

    # /orchestrate/devices
    devices_resource = get_or_create_resource(apigw, API_ID, orchestrate_id, 'devices')
    add_get_method_with_cors(apigw, API_ID, devices_resource['id'], lambda_arn)

    # /orchestrate/devices/{device_id}
    device_id_resource = get_or_create_resource(apigw, API_ID, devices_resource['id'], '{device_id}')
    add_get_method_with_cors(apigw, API_ID, device_id_resource['id'], lambda_arn)

    # /orchestrate/devices/{device_id}/summary
    summary_resource = get_or_create_resource(apigw, API_ID, device_id_resource['id'], 'summary')
    add_get_method_with_cors(apigw, API_ID, summary_resource['id'], lambda_arn)

    # Deploy to stage
    log(f"Deploying API Gateway to stage '{STAGE}'...")
    apigw.create_deployment(restApiId=API_ID, stageName=STAGE, description='Add /devices, /health GET routes')
    log("Deployment complete!", 'success')

    base_url = f"https://{API_ID}.execute-api.{args.region}.amazonaws.com/{STAGE}/orchestrate"
    log(f"New routes:")
    log(f"  GET {base_url}/health")
    log(f"  GET {base_url}/devices")
    log(f"  GET {base_url}/devices/{{device_id}}")
    log(f"  GET {base_url}/devices/{{device_id}}/summary")


if __name__ == '__main__':
    main()
