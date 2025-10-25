from typing import Annotated, Dict, Any, List, Literal, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge dictionaries for LangGraph state"""
    merged = left.copy()
    merged.update(right)
    return merged

class TaskAnalysis(BaseModel):
    """Analysis of the incoming task"""
    task_type: Literal["github", "kubernetes", "jenkins", "general"] = Field(
        description="Type of task"
    )
    priority: Literal["high", "medium", "low"] = Field(
        description="Task priority"
    )
    components: List[str] = Field(
        description="List of components/services involved"
    )
    reasoning: str = Field(
        description="Reasoning for the routing decision"
    )

class RoutingDecision(BaseModel):
    """Intelligent routing decision from orchestrator"""
    next_agent: Literal["github", "kubernetes", "jenkins", "summarizer", "unavailable_agent"] = Field(
        description="Next agent to route to"
    )
    reasoning: str = Field(
        description="Reasoning for the routing decision"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence in the routing decision"
    )
    context_needed: List[str] = Field(
        description="Context information needed for the next agent"
    )

class AgentResponse(BaseModel):
    """Response from an agent"""
    agent_name: str
    status: str = "success"
    findings: Dict[str, Any] = {}
    errors: List[Dict[str, Any]] = []
    next_actions: List[str] = []
    context_used: Optional[str] = Field(default=None, description="Context information used")
    raw_analysis: Optional[str] = Field(default=None, description="Raw analysis content")

class DevOpsWorkflowState(TypedDict):
    """State that flows through the workflow"""
    # Input
    user_prompt: str
    context: Dict[str, Any]
    
    # Analysis
    task_analysis: Optional[TaskAnalysis]
    
    # Agent responses
    github_response: Optional[AgentResponse]
    kubernetes_response: Optional[AgentResponse]
    jenkins_response: Optional[AgentResponse]
    
    # NEW: Correlation results
    correlation_analysis: Optional[Dict[str, Any]]
    
    # NEW: Historical solutions from RAG
    historical_solutions: Optional[Dict[str, Any]]
    
    # Intelligent routing
    routing_decisions: List[RoutingDecision]
    
    # Memory
    agent_memory: Annotated[Dict[str, Any], merge_dicts]
    execution_history: List[Dict[str, Any]]
    agent_status: Dict[str, str]
    
    # Final output
    summary: str
    action_items: List[str]
    status: str
    errors_found: List[Dict[str, Any]]
    final_response: Optional[Dict[str, Any]]
    
    # Confidence detection
    confidence: Optional[bool]
    confidence_level: Optional[str]
    confidence_reasoning: Optional[str]

