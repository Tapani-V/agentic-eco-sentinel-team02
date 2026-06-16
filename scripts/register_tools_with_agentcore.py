#!/usr/bin/env python3
"""
Register MCP tools (Lambda functions and App Runner service) with AgentCore Gateway.
Reads tool config (ARNs/URLs, schemas) and registers each tool via AgentCore Gateway API.
"""
import argparse
import json
import requests
import sys
from pathlib import Path


def load_config(config_path):
    with open(config_path, 'r') as f:
        return json.load(f)

def register_tool(agentcore_url, token, tool_payload):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    resp = requests.post(f"{agentcore_url}/tools/register", headers=headers, json=tool_payload)
    if resp.status_code == 200:
        print(f"✓ Registered tool: {tool_payload['name']}")
    else:
        print(f"✗ Failed to register tool: {tool_payload['name']} (Status: {resp.status_code})")
        print(resp.text)
    return resp

def verify_tools(agentcore_url, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{agentcore_url}/tools/list", headers=headers)
    if resp.status_code == 200:
        print("\nRegistered tools:")
        for tool in resp.json().get('tools', []):
            print(f"- {tool['name']} ({tool['type']})")
    else:
        print("✗ Failed to list tools.")
        print(resp.text)

def main():
    parser = argparse.ArgumentParser(description="Register MCP tools with AgentCore Gateway.")
    parser.add_argument('--config', required=True, help='Path to agentcore_tools_config.json')
    parser.add_argument('--agentcore-url', required=True, help='AgentCore Gateway API base URL (e.g., https://agentcore.example.com)')
    parser.add_argument('--token', required=True, help='Bearer token for AgentCore Gateway API')
    args = parser.parse_args()

    config = load_config(args.config)
    for tool in config['tools']:
        print(f"Registering tool: {tool['name']}...")
        register_tool(args.agentcore_url, args.token, tool)

    print("\nVerifying registration...")
    verify_tools(args.agentcore_url, args.token)

if __name__ == "__main__":
    main()
