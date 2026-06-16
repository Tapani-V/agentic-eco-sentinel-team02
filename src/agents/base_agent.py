#!/usr/bin/env python3
"""
BaseAgent - Abstract base class for all agents
Defines the contract that all agents must follow
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents
    
    All agents inherit from this class and implement the execute() method
    """
    
    def __init__(self, name: str, agent_type: str):
        """
        Initialize agent
        
        Args:
            name: Agent name (e.g., "HealthAgent")
            agent_type: Agent type (e.g., "health_analysis")
        """
        self.name = name
        self.agent_type = agent_type
        logger.info(f"Initialized {self.name} (type: {self.agent_type})")
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent task
        
        This method must be implemented by all subclasses
        
        Args:
            input_data: Input parameters (structure varies by agent)
        
        Returns:
            Result dictionary with standardized schema:
            {
                'device_id': str,
                'status': 'completed' or 'error',
                'error': str (optional),
                ... agent-specific fields
            }
        """
        pass
    
    def _log_execution(self, device_id: str, status: str, details: str = ""):
        """Helper to log agent execution"""
        logger.info(f"[{self.name}] {device_id}: {status} {details}")
