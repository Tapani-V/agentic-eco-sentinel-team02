#!/usr/bin/env python3
"""
Orchestration Workflow - LangGraph 4-node workflow (Week 2 Day 5-7)

Core workflow logic (microservices pattern - core + wrapper separation):
- Core: This file (OrchestrationWorkflow class) - LangGraph logic
- Wrapper: src/services/orchestrator/app.py (FastAPI service)

Architecture Pattern:
Follows same pattern as agents (src/agents/ + src/services/agent/):
├── Core logic: src/graph/workflow.py (pure Python, reusable)
└── Service wrapper: src/services/orchestrator/app.py (FastAPI, HTTP endpoints)

4-Node Workflow:
1. health_agent_node: Call HealthAgent service (port 8001)
2. router_node: Conditional routing (cost optimization)
3. diagnosis_agent_node: Call DiagnosisAgent service (port 8002)
4. aggregator_node: Combine results
"""

import logging
import httpx
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    """Shared state across workflow nodes."""
    device_id: str
    equipment_type: str
    current_reading: Dict[str, Any]
    
    # From HealthAgent (Step 1)
    health_status: str
    degradation_score: float
    anomalies: List[str]
    
    # From DiagnosisAgent (Step 3, optional)
    diagnosis: str
    confidence: float
    severity: str
    action: str
    action_taken: str
    tool_results: Dict[str, Any]
    llm_used: bool
    
    # Recommendation fields from DiagnosisAgent (for dashboard display)
    insights: str
    immediate_actions: List[str]
    predicted_failure_date: Optional[str]
    recommendation_details: str
    
    # Routing
    route: str  # "end" or "diagnose"
    
    # Metadata
    start_time: float
    
    # Agent Tracking (Phase 2.8 - Agent Usage Visibility)
    agents_used: List[str]  # Which agents were called (e.g., ['health_agent', 'diagnosis_agent'])
    mcp_tools_used: List[str]  # Which MCP tools were invoked (e.g., ['get-spare-parts', 'schedule-maintenance'])


class OrchestrationWorkflow:
    """
    LangGraph-based orchestration workflow
    
    Week 2 Day 5-7 Implementation:
    - 4 nodes with HTTP-based service calls (microservices architecture)
    - Async processing for production performance
    - Cost optimization through conditional routing
    
    Usage:
        workflow = OrchestrationWorkflow(
            health_agent_url="http://localhost:8001",
            diagnosis_agent_url="http://localhost:8002"
        )
        result = await workflow.run(initial_state)
    """
    
    def __init__(self, health_agent_url: str, diagnosis_agent_url: str):
        """Initialize workflow with service URLs.
        
        Args:
            health_agent_url: Base URL of HealthAgent service (e.g., http://localhost:8001)
            diagnosis_agent_url: Base URL of DiagnosisAgent service (e.g., http://localhost:8002)
        """
        self.health_agent_url = health_agent_url
        self.diagnosis_agent_url = diagnosis_agent_url
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("health_agent", self._health_agent_node)
        workflow.add_node("router", self._router_node)
        workflow.add_node("diagnosis_agent", self._diagnosis_agent_node)
        workflow.add_node("aggregator", self._aggregator_node)
        
        # Add edges
        workflow.add_edge("health_agent", "router")
        
        # Conditional routing: router decides next step
        def route_condition(state: WorkflowState) -> str:
            return state['route']
        
        workflow.add_conditional_edges(
            "router",
            route_condition,
            {
                'end': 'aggregator',           # Skip DiagnosisAgent (healthy)
                'diagnose': 'diagnosis_agent'  # Call DiagnosisAgent (needs investigation)
            }
        )
        
        # After diagnosis, always go to aggregator
        workflow.add_edge("diagnosis_agent", "aggregator")
        
        # Aggregator is final node
        workflow.add_edge("aggregator", END)
        
        # Set entry point
        workflow.set_entry_point("health_agent")
        
        return workflow.compile()
    
    async def _health_agent_node(self, state: WorkflowState) -> WorkflowState:
        """Node 1: Call HealthAgent service
        
        Pure health classification:
        - Input: sensor data
        - Output: health_status (healthy/warning/critical)
        - No tools called, no LLM called
        """
        try:
            logger.info(f"[NODE 1] HealthAgent: Analyzing {state['device_id']}")
            
            # Track that HealthAgent was used
            state['agents_used'].append('HealthAgent')
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.health_agent_url}/analyze",
                    json={
                        "device_id": state['device_id'],
                        "equipment_type": state['equipment_type'],
                        "current_reading": state['current_reading']
                    }
                )
                response.raise_for_status()
                
                result = response.json()
                
                state['health_status'] = result['health_status']
                state['degradation_score'] = result['degradation_score']
                state['anomalies'] = result.get('anomalies', [])
                
                logger.info(f"  → Health: {state['health_status']}, Score: {state['degradation_score']:.2f}")
                return state
            
        except Exception as e:
            logger.error(f"HealthAgent call failed: {e}", exc_info=True)
            raise
    
    async def _router_node(self, state: WorkflowState) -> WorkflowState:
        """Node 2: Router - Conditional routing
        
        COST OPTIMIZATION: If device is healthy, skip DiagnosisAgent
        - Saves time (no LLM calls, no tool calls)
        - Saves cost (no DiagnosisAgent processing)
        - Route to END (aggregator)
        
        If not healthy, route to DiagnosisAgent for investigation
        """
        logger.info(f"[NODE 2] Router: Routing {state['device_id']}")
        
        if state['health_status'] == 'healthy':
            logger.info(f"  → Device HEALTHY: SKIP DiagnosisAgent (cost optimization)")
            state['route'] = 'end'
            state['diagnosis'] = 'Device operating normally'
            state['confidence'] = 1.0
            state['severity'] = 'low'
            state['action'] = 'MONITOR_ONLY'
            state['action_taken'] = 'No action required'
            state['llm_used'] = False
            state['tool_results'] = {}
        else:
            logger.info(f"  → Device {state['health_status'].upper()}: CALL DiagnosisAgent")
            state['route'] = 'diagnose'
        
        return state
    
    async def _diagnosis_agent_node(self, state: WorkflowState) -> WorkflowState:
        """Node 3: Call DiagnosisAgent service (conditional, only if not healthy)
        
        4-step process:
        1. Pattern matching (equipment-specific rules)
        2. Confidence check (≥0.85 = trust, <0.85 = LLM)
        3. Optional LLM enhancement
        4. Execute action (MCP tools if needed)
        """
        try:
            logger.info(f"[NODE 3] DiagnosisAgent: Diagnosing {state['device_id']}")
            
            # Track that DiagnosisAgent was used
            state['agents_used'].append('DiagnosisAgent')
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.diagnosis_agent_url}/diagnose",
                    json={
                        "device_id": state['device_id'],
                        "equipment_type": state['equipment_type'],
                        "health_status": state['health_status'],
                        "degradation_score": state['degradation_score'],
                        "anomalies": state['anomalies'],
                        "current_reading": state['current_reading']
                    }
                )
                response.raise_for_status()
                
                result = response.json()
                
                state['diagnosis'] = result['diagnosis']
                state['confidence'] = result['confidence']
                state['severity'] = result['severity']
                state['action'] = result['action']
                state['action_taken'] = result['action_taken']
                state['tool_results'] = result.get('tool_results', {})
                state['llm_used'] = result.get('llm_used', False)
                
                # Extract recommendation fields for dashboard
                state['insights'] = result.get('insights', '')
                state['immediate_actions'] = result.get('immediate_actions', [])
                state['predicted_failure_date'] = result.get('predicted_failure_date')
                state['recommendation_details'] = result.get('recommendation_details', '')
                
                # Track MCP tools that were used (extracted from tool_results)
                tools_used = result.get('tool_results', {})
                for tool_name in tools_used.keys():
                    # Filter out error entries and other non-tool entries
                    if tool_name not in ['error'] and not tool_name.startswith('_'):
                        state['mcp_tools_used'].append(tool_name)
                
                logger.info(f"  → Action: {state['action']}, Confidence: {state['confidence']:.2f}")
                return state
            
        except Exception as e:
            logger.error(f"DiagnosisAgent call failed: {e}", exc_info=True)
            raise
    
    async def _aggregator_node(self, state: WorkflowState) -> WorkflowState:
        """Node 4: Aggregator - Combine results
        
        Final processing before returning to client
        """
        logger.info(f"[NODE 4] Aggregator: Finalizing report for {state['device_id']}")
        # State is already prepared by previous nodes
        return state
    
    async def run(self, initial_state: WorkflowState) -> Dict[str, Any]:
        """Run the workflow asynchronously.
        
        Args:
            initial_state: Initial workflow state
            
        Returns:
            Final workflow state with results
        """
        return await self.graph.ainvoke(initial_state)
