#!/usr/bin/env python3
"""
AgentCore Runtime Entry Point Wrapper

This script is the Docker entry point for agents deployed to AWS Bedrock
AgentCore Runtime. AgentCore Runtime invokes containers over HTTP, POSTing
the payload to `/invocations` and health-checking `/ping` on port 8080
(see bedrock_agentcore.runtime.BedrockAgentCoreApp). This wrapper loads the
Lambda-style handler module (which exposes `lambda_handler(event, context)`)
and exposes it via BedrockAgentCoreApp so it can be invoked correctly.

Usage:
    python agentcore_entrypoint.py <handler_module> [--port PORT]

Example:
    python agentcore_entrypoint.py src.services.health_agent.handler --port 8080
"""

import argparse
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='AgentCore Runtime Entry Point')
    parser.add_argument('handler_module', help='Python module path to handler (e.g., src.services.health_agent.handler)')
    parser.add_argument('--port', type=int, default=8080, help='Port to serve on (default: 8080)')

    args = parser.parse_args()

    logger.info("AgentCore Entry Point")
    logger.info(f"Handler Module: {args.handler_module}")
    logger.info(f"Port: {args.port}")

    # Dynamically import the handler module itself (not a function name -
    # the full dotted path already points at the module, e.g.
    # "src.services.health_agent.handler").
    logger.info(f"Importing {args.handler_module}...")
    module = __import__(args.handler_module, fromlist=[''])

    if hasattr(module, 'lambda_handler'):
        handler_func = module.lambda_handler
    elif hasattr(module, 'handler'):
        handler_func = module.handler
    else:
        raise AttributeError(f"No handler function found in {args.handler_module}")

    logger.info(f"✓ Handler loaded: {handler_func}")

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload):
        """Bridge AgentCore's HTTP invocation payload to the Lambda-style handler."""
        logger.info(f"Received payload: {str(payload)[:200]}")
        result = handler_func(payload, None)
        logger.info(f"Handler result: {str(result)[:200]}")
        return result

    logger.info(f"Starting AgentCore HTTP server on port {args.port}...")
    app.run(port=args.port)


if __name__ == '__main__':
    main()
