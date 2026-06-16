"""
GatewayClient exceptions.
"""


class GatewayError(Exception):
    """Base exception for gateway errors."""
    pass


class TokenError(GatewayError):
    """Failed to acquire or refresh Cognito token."""
    pass


class ToolCallError(GatewayError):
    """Tool call failed after retries."""
    
    def __init__(self, tool_name: str, message: str, status_code: int = None):
        self.tool_name = tool_name
        self.status_code = status_code
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class ToolNotFoundError(GatewayError):
    """Requested tool not found in gateway."""
    
    def __init__(self, tool_name: str, available_tools: list = None):
        self.tool_name = tool_name
        self.available_tools = available_tools or []
        super().__init__(f"Tool '{tool_name}' not found. Available: {self.available_tools}")
