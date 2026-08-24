#!/usr/bin/env python3
"""
Orchestration Workflow - AgentCore Compatible Version

This is the AWS AgentCore Runtime compatible version of the workflow, used by
src/services/orchestrator/handler.py for the "analyze"/"get_device" actions.
Instead of calling agents via HTTP, it uses boto3 to invoke them via bedrock-agentcore.

Core differences from workflow.py (the old local docker-compose version):
- Uses boto3.client('bedrock-agentcore').invoke_agent_runtime() instead of httpx
- Generates session IDs with required length (>= 33 chars)
- Handles StreamingBody responses properly
"""

import logging
import json
import uuid
import boto3
from datetime import datetime
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
    confidence_rule_based: Optional[float]
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
    
    # Agent Tracking
    agents_used: List[str]
    mcp_tools_used: List[str]


class AgentCoreworkflow:
    """
    LangGraph-based orchestration workflow for AWS AgentCore Runtime
    
    Uses boto3 to invoke other agents via bedrock-agentcore service.
    """
    
    def __init__(self, health_agent_runtime_id: str, diagnosis_agent_runtime_id: str, account_id: str, region: str = "us-east-1"):
        """Initialize workflow with agent runtime IDs.
        
        Args:
            health_agent_runtime_id: Runtime ID of health agent (e.g., "health_agent_runtime-fAr31a5AEi")
            diagnosis_agent_runtime_id: Runtime ID of diagnosis agent (e.g., "diagnosis_agent_runtime-r8AcIc5zbG")
            account_id: AWS account ID
            region: AWS region (default: us-east-1)
        """
        self.health_agent_runtime_id = health_agent_runtime_id
        self.diagnosis_agent_runtime_id = diagnosis_agent_runtime_id
        self.account_id = account_id
        self.region = region
        
        # Initialize boto3 client
        self.agentcore_client = boto3.client('bedrock-agentcore', region_name=region)
        
        logger.info(f"AgentCore Workflow initialized")
        logger.info(f"  Health Agent Runtime: {health_agent_runtime_id}")
        logger.info(f"  Diagnosis Agent Runtime: {diagnosis_agent_runtime_id}")
        
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
        
        # Conditional routing
        def route_condition(state: WorkflowState) -> str:
            return state['route']
        
        workflow.add_conditional_edges(
            "router",
            route_condition,
            {
                'end': 'aggregator',
                'diagnose': 'diagnosis_agent'
            }
        )
        
        workflow.add_edge("diagnosis_agent", "aggregator")
        workflow.add_edge("aggregator", END)
        
        workflow.set_entry_point("health_agent")
        
        return workflow.compile()
    
    def _invoke_agent(self, runtime_id: str, payload: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Invoke an agent via boto3 bedrock-agentcore.
        
        Args:
            runtime_id: Runtime ID of the agent
            payload: Payload to send to agent
            session_id: Session ID (must be >= 33 chars)
        
        Returns:
            Parsed response from agent
        """
        try:
            # Construct ARN
            agent_runtime_arn = f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:runtime/{runtime_id}"
            
            logger.info(f"  Invoking {runtime_id} via boto3")
            
            # Invoke agent
            response = self.agentcore_client.invoke_agent_runtime(
                agentRuntimeArn=agent_runtime_arn,
                runtimeSessionId=session_id,
                payload=json.dumps(payload)
            )
            
            # Read and parse response
            response_body = response['response'].read()
            result = json.loads(response_body.decode('utf-8'))
            
            logger.info(f"  → {runtime_id} response received")
            
            # Agent handlers return Lambda-style {"statusCode": ..., "body": {...}}
            # responses (see src/services/<agent>/handler.py's @app.entrypoint
            # function, which returns this envelope as-is). Unwrap "body" to get
            # the actual agent output.
            if isinstance(result, dict) and 'body' in result:
                if result.get('statusCode', 200) >= 400:
                    error_body = result['body']
                    raise RuntimeError(f"{runtime_id} returned error: {error_body}")
                return result['body']
            
            return result
            
        except Exception as e:
            logger.error(f"Agent invocation failed ({runtime_id}): {e}", exc_info=True)
            raise
    
    async def _health_agent_node(self, state: WorkflowState) -> WorkflowState:
        """Node 1: Call HealthAgent via boto3."""
        try:
            logger.info(f"[NODE 1] HealthAgent: Analyzing {state['device_id']}")
            state['agents_used'].append('HealthAgent')
            
            # Session ID must be >= 33 chars regardless of device_id length -
            # pad with a uuid4 hex suffix to guarantee this.
            session_id = f"health-{state['device_id']}-{uuid.uuid4().hex}"
            
            result = self._invoke_agent(
                self.health_agent_runtime_id,
                {
                    "device_id": state['device_id'],
                    "equipment_type": state['equipment_type'],
                    "current_reading": state['current_reading']
                },
                session_id
            )
            
            state['health_status'] = result['health_status']
            state['degradation_score'] = result['degradation_score']
            state['anomalies'] = result.get('anomalies', [])
            
            logger.info(f"  → Health: {state['health_status']}, Score: {state['degradation_score']:.2f}")
            return state
            
        except Exception as e:
            logger.error(f"HealthAgent call failed: {e}", exc_info=True)
            raise
    
    async def _router_node(self, state: WorkflowState) -> WorkflowState:
        """Node 2: Router - Conditional routing."""
        logger.info(f"[NODE 2] Router: Routing {state['device_id']}")
        
        if state['health_status'] == 'healthy':
            logger.info(f"  → Device HEALTHY: SKIP DiagnosisAgent (cost optimization)")
            state['route'] = 'end'
            state['diagnosis'] = 'Device operating normally'
            state['confidence'] = 1.0
            state['confidence_rule_based'] = 1.0
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
        """Node 3: Call DiagnosisAgent via boto3."""
        try:
            logger.info(f"[NODE 3] DiagnosisAgent: Diagnosing {state['device_id']}")
            state['agents_used'].append('DiagnosisAgent')
            
            # Session ID must be >= 33 chars regardless of device_id length -
            # pad with a uuid4 hex suffix to guarantee this.
            session_id = f"diagnosis-{state['device_id']}-{uuid.uuid4().hex}"
            
            result = self._invoke_agent(
                self.diagnosis_agent_runtime_id,
                {
                    "device_id": state['device_id'],
                    "equipment_type": state['equipment_type'],
                    "health_status": state['health_status'],
                    "degradation_score": state['degradation_score'],
                    "anomalies": state['anomalies'],
                    "current_reading": state['current_reading']
                },
                session_id
            )
            
            state['diagnosis'] = result['diagnosis']
            state['confidence'] = result['confidence']
            state['confidence_rule_based'] = result.get('confidence_rule_based', result['confidence'])
            state['severity'] = result.get('severity', 'medium')
            state['action'] = result['action']
            state['action_taken'] = result.get('action_taken', '')
            state['tool_results'] = result.get('tool_results', {})
            state['llm_used'] = result.get('llm_used', False)
            state['insights'] = result.get('insights', '')
            state['immediate_actions'] = result.get('immediate_actions', [])
            state['predicted_failure_date'] = result.get('predicted_failure_date')
            state['recommendation_details'] = result.get('recommendation_details', '')
            
            # DiagnosisAgent returns 'tool_results' (e.g. {'create-work-order': {...}}),
            # not a 'mcp_tools_used' list - derive it from the tool_results keys.
            if state['tool_results']:
                state['mcp_tools_used'].extend(state['tool_results'].keys())
            
            logger.info(f"  → Diagnosis: {state['diagnosis']}, Action: {state['action']}")
            return state
            
        except Exception as e:
            logger.error(f"DiagnosisAgent call failed: {e}", exc_info=True)
            raise
    
    async def _aggregator_node(self, state: WorkflowState) -> WorkflowState:
        """Node 4: Aggregator - Final state preparation."""
        logger.info(f"[NODE 4] Aggregator: Finalizing results for {state['device_id']}")
        
        # All required fields should be set by this point
        return state
    
    async def run(self, initial_state: WorkflowState) -> WorkflowState:
        """Run the workflow.
        
        Args:
            initial_state: Initial workflow state
        
        Returns:
            Final workflow state with all results
        """
        return await self.graph.ainvoke(initial_state)
