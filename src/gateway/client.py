"""
GatewayClient - Shared module for AgentCore Gateway tool calls.

Handles:
- Cognito token acquisition (client_credentials grant)
- Token caching with proactive refresh
- Gateway HTTP calls (tools/list, tools/call)
- Error handling and retries
"""

import os
import time
import logging
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from dotenv import load_dotenv

from .exceptions import GatewayError, TokenError, ToolCallError, ToolNotFoundError


# Load .agentcore.env from project root
_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".agentcore.env"
if _env_file.exists():
    load_dotenv(_env_file)

logger = logging.getLogger(__name__)


class GatewayClient:
    """
    Client for calling MCP tools via AgentCore Gateway.
    
    Usage:
        gateway = GatewayClient()
        
        # List available tools
        tools = gateway.list_tools()
        
        # Call a tool (short name or full name both work)
        result = gateway.call_tool("get_spare_parts", {"part_type": "bearing"})
    """
    
    # Refresh token 5 minutes before expiry
    TOKEN_REFRESH_BUFFER_SECONDS = 300
    
    def __init__(self):
        """Initialize client and load config from environment."""
        # Required config
        self.client_id = os.getenv("COGNITO_APP_CLIENT_ID")
        self.client_secret = os.getenv("COGNITO_APP_CLIENT_SECRET")
        self.token_endpoint = os.getenv("COGNITO_TOKEN_ENDPOINT")
        self.scope = os.getenv("COGNITO_SCOPE", "agentcore/invoke")
        self.gateway_url = os.getenv("GATEWAY_URL")
        
        # Validate config
        self._validate_config()
        
        # Token cache
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        
        # Tools cache (populated on first list_tools call)
        self._tools_cache: Optional[List[Dict]] = None
    
    def _validate_config(self):
        """Ensure all required environment variables are set."""
        missing = []
        if not self.client_id:
            missing.append("COGNITO_APP_CLIENT_ID")
        if not self.client_secret:
            missing.append("COGNITO_APP_CLIENT_SECRET")
        if not self.token_endpoint:
            missing.append("COGNITO_TOKEN_ENDPOINT")
        if not self.gateway_url:
            missing.append("GATEWAY_URL")
        
        if missing:
            raise GatewayError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Check .agentcore.env file."
            )
    
    # -------------------------------------------------------------------------
    # Token Management
    # -------------------------------------------------------------------------
    
    def _get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if needed.
        
        Uses proactive refresh: gets new token 5 minutes before expiry
        to avoid mid-request failures.
        """
        now = time.time()
        
        # Check if current token is still valid (with buffer)
        if self._token and (self._token_expiry - now) > self.TOKEN_REFRESH_BUFFER_SECONDS:
            return self._token
        
        # Need new token
        logger.info("Fetching new Cognito access token...")
        self._token, self._token_expiry = self._fetch_new_token()
        logger.info(f"Token acquired, expires in {int(self._token_expiry - now)} seconds")
        
        return self._token
    
    def _fetch_new_token(self) -> Tuple[str, float]:
        """
        Fetch new token from Cognito using client_credentials grant.
        
        Returns:
            Tuple of (access_token, expiry_timestamp)
        """
        try:
            response = requests.post(
                self.token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": self.scope,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            
            if response.status_code != 200:
                raise TokenError(
                    f"Token request failed: {response.status_code} - {response.text}"
                )
            
            data = response.json()
            access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)  # Default 1 hour
            expiry_timestamp = time.time() + expires_in
            
            return access_token, expiry_timestamp
            
        except requests.RequestException as e:
            raise TokenError(f"Token request failed: {e}")
    
    # -------------------------------------------------------------------------
    # Gateway Calls
    # -------------------------------------------------------------------------
    
    def list_tools(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get list of available tools from gateway.
        
        Args:
            force_refresh: If True, bypass cache and fetch from gateway
            
        Returns:
            List of tool definitions with name, description, inputSchema
        """
        if self._tools_cache and not force_refresh:
            return self._tools_cache
        
        token = self._get_valid_token()
        
        try:
            response = requests.post(
                self.gateway_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": "list-tools",
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            
            if response.status_code == 401:
                # Token might be invalid, try once with fresh token
                logger.warning("Got 401, refreshing token and retrying...")
                self._token = None
                token = self._get_valid_token()
                response = requests.post(
                    self.gateway_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/list",
                        "id": "list-tools",
                    },
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
            
            if response.status_code != 200:
                raise GatewayError(
                    f"tools/list failed: {response.status_code} - {response.text}"
                )
            
            data = response.json()
            if "error" in data:
                raise GatewayError(f"tools/list error: {data['error']}")
            
            self._tools_cache = data.get("result", {}).get("tools", [])
            return self._tools_cache
            
        except requests.RequestException as e:
            raise GatewayError(f"tools/list request failed: {e}")
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool via the gateway.
        
        Args:
            tool_name: Short name (e.g., "get_spare_parts") or full gateway name
            arguments: Tool input arguments
            
        Returns:
            Tool result (parsed from response)
        """
        # Resolve short name to full gateway name
        full_name = self.resolve_tool_name(tool_name)
        
        token = self._get_valid_token()
        
        logger.info(f"Calling tool: {full_name} with args: {arguments}")
        
        try:
            response = requests.post(
                self.gateway_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": full_name,
                        "arguments": arguments,
                    },
                    "id": f"call-{full_name}",
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=60,  # Tool calls may take longer
            )
            
            if response.status_code == 401:
                # Token might be invalid, try once with fresh token
                logger.warning("Got 401 on tool call, refreshing token and retrying...")
                self._token = None
                token = self._get_valid_token()
                response = requests.post(
                    self.gateway_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {
                            "name": full_name,
                            "arguments": arguments,
                        },
                        "id": f"call-{full_name}",
                    },
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=60,
                )
            
            if response.status_code != 200:
                raise ToolCallError(
                    tool_name=full_name,
                    message=f"HTTP {response.status_code}: {response.text}",
                    status_code=response.status_code,
                )
            
            data = response.json()
            
            if "error" in data:
                raise ToolCallError(
                    tool_name=full_name,
                    message=str(data["error"]),
                )
            
            # Extract result content
            result = data.get("result", {})
            content = result.get("content", [])
            
            # Parse JSON from text content if present
            if content and isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        import json
                        try:
                            return json.loads(item.get("text", "{}"))
                        except json.JSONDecodeError:
                            return {"raw_text": item.get("text")}
            
            return result
            
        except requests.RequestException as e:
            raise ToolCallError(tool_name=full_name, message=str(e))
    
    def resolve_tool_name(self, short_name: str) -> str:
        """
        Resolve a short tool name to the full gateway name.
        
        Examples:
            "get_spare_parts" → "get-spare-parts___get_spare_parts"
            "schedule_maintenance" → "schedule-maintenance___schedule_maintenance"
            
        If already a full name (contains ___), returns as-is.
        """
        if "___" in short_name:
            return short_name  # Already full name
        
        # Get tools list (cached)
        tools = self.list_tools()
        
        # Find matching tool
        for tool in tools:
            tool_full_name = tool.get("name", "")
            # Match if short_name appears after the ___
            if tool_full_name.endswith(f"___{short_name}"):
                return tool_full_name
            # Also match if it's a substring (flexible matching)
            if short_name.replace("-", "_") in tool_full_name.replace("-", "_"):
                return tool_full_name
        
        # Not found - raise with available tools
        available = [t.get("name") for t in tools]
        raise ToolNotFoundError(short_name, available)
