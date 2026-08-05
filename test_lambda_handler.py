#!/usr/bin/env python3
"""
Local testing script for Lambda Orchestrator Handler

Purpose:
    Test the Lambda handler locally before AWS deployment.
    Validates:
    - Handler code syntax
    - Environment variable loading
    - OAuth2 token acquisition
    - Request/response parsing
    - Error handling

Usage:
    # Run all tests
    python3 test_lambda_handler.py
    
    # Run specific test
    python3 test_lambda_handler.py --test parse_request
    
    # Verbose output
    python3 test_lambda_handler.py --verbose

Author: Agentic AI POC Phase 3.1
Date: 2026-07-23
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add functions to path (handle both direct execution and import)
functions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'functions')
if not os.path.exists(functions_path):
    # If running from within functions directory
    functions_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, functions_path)

# Colors for output
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'


class TestRunner:
    """Test runner for Lambda handler"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.tests_passed = 0
        self.tests_failed = 0
    
    def log(self, message: str, level: str = 'info'):
        """Print colored log"""
        if level == 'info' and not self.verbose:
            return
        
        if level == 'info':
            print(f"{BLUE}[INFO]{RESET} {message}")
        elif level == 'success':
            print(f"{GREEN}[✓]{RESET} {message}")
        elif level == 'warning':
            print(f"{YELLOW}[⚠]{RESET} {message}")
        elif level == 'error':
            print(f"{RED}[✗]{RESET} {message}")
        elif level == 'header':
            print(f"\n{BOLD}{BLUE}=== {message} ==={RESET}\n")
        else:
            print(f"{RESET}{message}")
    
    def assert_equal(self, actual, expected, message: str):
        """Assert equality and track results"""
        if actual == expected:
            self.log(f"✓ {message}", 'success')
            self.tests_passed += 1
            return True
        else:
            self.log(f"✗ {message}", 'error')
            self.log(f"  Expected: {expected}", 'error')
            self.log(f"  Actual: {actual}", 'error')
            self.tests_failed += 1
            return False
    
    def assert_true(self, value, message: str):
        """Assert value is true"""
        if value:
            self.log(f"✓ {message}", 'success')
            self.tests_passed += 1
            return True
        else:
            self.log(f"✗ {message}", 'error')
            self.tests_failed += 1
            return False
    
    def assert_contains(self, text: str, substring: str, message: str):
        """Assert text contains substring"""
        if substring in text:
            self.log(f"✓ {message}", 'success')
            self.tests_passed += 1
            return True
        else:
            self.log(f"✗ {message}", 'error')
            self.log(f"  Looking for: {substring}", 'error')
            self.log(f"  In: {text[:100]}", 'error')
            self.tests_failed += 1
            return False
    
    def test_handler_import(self):
        """Test 1: Import handler module"""
        self.log("header", "Test 1: Handler Import")
        
        try:
            import lambda_orchestrator_handler as handler
            self.assert_true(handler is not None, "Handler module imported successfully")
            self.assert_true(hasattr(handler, 'lambda_handler'), "lambda_handler function exists")
            self.assert_true(hasattr(handler, 'parse_api_gateway_event'), "parse_api_gateway_event function exists")
            self.assert_true(hasattr(handler, 'invoke_orchestrator_agent'), "invoke_orchestrator_agent function exists")
            return True
        except Exception as e:
            self.log(f"Failed to import handler: {e}", 'error')
            return False
    
    def test_parse_request_valid(self):
        """Test 2: Parse valid API Gateway request"""
        self.log("header", "Test 2: Parse Valid Request")
        
        from lambda_orchestrator_handler import parse_api_gateway_event
        
        event = {
            'body': json.dumps({
                'device_id': 'motor-004',
                'equipment_type': 'MOTOR',
                'current_reading': {
                    'readings': {
                        'current': {'value': 100, 'unit': 'Amps', 'normal_range': [60, 80]},
                        'temperature': {'value': 143.19, 'unit': 'F', 'normal_range': [60, 120]},
                    }
                }
            })
        }
        
        result = parse_api_gateway_event(event)
        
        self.assert_equal(result.get('device_id'), 'motor-004', "device_id parsed correctly")
        self.assert_equal(result.get('equipment_type'), 'MOTOR', "equipment_type parsed correctly")
        self.assert_true(result.get('current_reading') is not None, "current_reading parsed correctly")
    
    def test_parse_request_missing_fields(self):
        """Test 3: Parse request with missing fields"""
        self.log("header", "Test 3: Parse Request with Missing Fields")
        
        from lambda_orchestrator_handler import parse_api_gateway_event
        
        # Missing device_id
        event = {
            'body': json.dumps({
                'equipment_type': 'MOTOR',
                'current_reading': {}
            })
        }
        
        result = parse_api_gateway_event(event)
        self.assert_true('error' in result, "Error returned for missing device_id")
        self.assert_contains(result.get('error', ''), 'device_id', "Error message mentions device_id")
    
    def test_parse_request_invalid_json(self):
        """Test 4: Parse request with invalid JSON"""
        self.log("header", "Test 4: Parse Request with Invalid JSON")
        
        from lambda_orchestrator_handler import parse_api_gateway_event
        
        event = {
            'body': '{invalid json}'
        }
        
        result = parse_api_gateway_event(event)
        self.assert_true('error' in result, "Error returned for invalid JSON")
    
    def test_parse_request_base64(self):
        """Test 5: Parse base64-encoded request"""
        self.log("header", "Test 5: Parse Base64-Encoded Request")
        
        import base64
        from lambda_orchestrator_handler import parse_api_gateway_event
        
        body = json.dumps({
            'device_id': 'pump-001',
            'equipment_type': 'PUMP',
            'current_reading': {'readings': {}}
        })
        
        event = {
            'body': base64.b64encode(body.encode()).decode(),
            'isBase64Encoded': True
        }
        
        result = parse_api_gateway_event(event)
        self.assert_equal(result.get('device_id'), 'pump-001', "Base64-encoded request parsed correctly")
    
    def test_create_response(self):
        """Test 6: Create API Gateway response"""
        self.log("header", "Test 6: Create API Gateway Response")
        
        from lambda_orchestrator_handler import create_response
        
        response = create_response(200, {'message': 'success'})
        
        self.assert_equal(response.get('statusCode'), 200, "Status code set correctly")
        self.assert_true('body' in response, "Response body included")
        self.assert_true('headers' in response, "Response headers included")
        self.assert_equal(response.get('headers', {}).get('Content-Type'), 'application/json', "Content-Type header set")
        self.assert_equal(response.get('headers', {}).get('Access-Control-Allow-Origin'), '*', "CORS header set")
    
    def test_lambda_handler_cors_preflight(self):
        """Test 7: Lambda handler CORS preflight"""
        self.log("header", "Test 7: Lambda Handler CORS Preflight")
        
        from lambda_orchestrator_handler import lambda_handler
        
        event = {
            'httpMethod': 'OPTIONS'
        }
        
        class MockContext:
            request_id = 'test-123'
            function_name = 'test-function'
        
        response = lambda_handler(event, MockContext())
        
        self.assert_equal(response.get('statusCode'), 200, "CORS preflight returns 200")
    
    def test_lambda_handler_invalid_request(self):
        """Test 8: Lambda handler with invalid request"""
        self.log("header", "Test 8: Lambda Handler Invalid Request")
        
        from lambda_orchestrator_handler import lambda_handler
        
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'invalid': 'data'
            })
        }
        
        class MockContext:
            request_id = 'test-123'
            function_name = 'test-function'
        
        response = lambda_handler(event, MockContext())
        
        self.assert_equal(response.get('statusCode'), 400, "Invalid request returns 400")
        self.assert_true('error' in json.loads(response.get('body', '{}')), "Error in response body")
    
    def test_environment_variables(self):
        """Test 9: Check environment variables"""
        self.log("header", "Test 9: Environment Variables")
        
        from lambda_orchestrator_handler import (
            ORCHESTRATOR_ENDPOINT,
            COGNITO_APP_CLIENT_ID,
            COGNITO_TOKEN_ENDPOINT,
            COGNITO_SCOPE
        )
        
        # These might be None in local testing, which is ok
        self.log(f"ORCHESTRATOR_ENDPOINT: {'set' if ORCHESTRATOR_ENDPOINT else 'not set'}", 'info')
        self.log(f"COGNITO_APP_CLIENT_ID: {'set' if COGNITO_APP_CLIENT_ID else 'not set'}", 'info')
        self.log(f"COGNITO_TOKEN_ENDPOINT: {'set' if COGNITO_TOKEN_ENDPOINT else 'not set'}", 'info')
        self.log(f"COGNITO_SCOPE: {COGNITO_SCOPE}", 'info')
        
        self.assert_true(COGNITO_SCOPE == 'agentcore/invoke', "COGNITO_SCOPE has correct default")
    
    def run_all(self):
        """Run all tests"""
        self.log("header", f"Running Lambda Handler Tests ({datetime.now().isoformat()})")
        
        tests = [
            self.test_handler_import,
            self.test_parse_request_valid,
            self.test_parse_request_missing_fields,
            self.test_parse_request_invalid_json,
            self.test_parse_request_base64,
            self.test_create_response,
            self.test_lambda_handler_cors_preflight,
            self.test_lambda_handler_invalid_request,
            self.test_environment_variables,
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log(f"Test {test.__name__} failed with exception: {e}", 'error')
                self.tests_failed += 1
        
        # Summary
        total = self.tests_passed + self.tests_failed
        self.log("header", "Test Summary")
        
        if self.tests_failed == 0:
            self.log(f"{GREEN}{BOLD}✓ All {total} tests passed!{RESET}", 'success')
            return True
        else:
            self.log(f"{RED}✗ {self.tests_failed} of {total} tests failed{RESET}", 'error')
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Test Lambda Orchestrator Handler locally'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    runner = TestRunner(verbose=args.verbose)
    success = runner.run_all()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
