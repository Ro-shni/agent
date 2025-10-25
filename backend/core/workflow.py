"""
Manages the LangGraph workflow, including node definitions and graph construction.
"""
from langgraph.graph import StateGraph, START, END
from ..models.workflow import DevOpsWorkflowState
from .routing import RoutingLogic
from .node import Nodes
class WorkflowManager:
    """Builds and manages the LangGraph workflow."""

    def __init__(self, orchestrator_nodes: Nodes):
        # self.nodes = orchestrator_nodes
        self.nodes=orchestrator_nodes
        self.router = RoutingLogic()
        self.workflow_app = self.build_workflow()
        # self.orchestrator = orchestrator_nodes

    def build_workflow(self) -> StateGraph:
        """Build the INTELLIGENT LangGraph workflow with FIXED routing"""
        
        workflow = StateGraph(DevOpsWorkflowState)
        
        # Add nodes
        workflow.add_node("orchestrator", self.nodes.orchestrator_node)
        workflow.add_node("github_agent", self.nodes.github_agent_node)
        workflow.add_node("kubernetes_agent", self.nodes.kubernetes_agent_node)
        workflow.add_node("jenkins_agent", self.nodes.jenkins_agent_node)
        workflow.add_node("intelligent_summarizer", self.nodes.intelligent_summarizer_node)
        workflow.add_node("unavailable_agent", self.nodes.unavailable_agent_node)

        # Set entry point
        workflow.add_edge(START, "orchestrator")
        
        # INTELLIGENT ROUTING: Orchestrator decides dynamically
        workflow.add_conditional_edges(
            "orchestrator",
            self.router.intelligent_routing_logic,
            {
                "github": "github_agent",
                "kubernetes": "kubernetes_agent",
                "jenkins": "jenkins_agent",
                "summarizer": "intelligent_summarizer",
                "unavailable_agent": "unavailable_agent",

            }
        )
        
        # FIXED ROUTING: Each agent can route back to orchestrator or to summarizer
        workflow.add_conditional_edges(
            "github_agent",
            self.router.post_github_routing_fixed,
            {
                "orchestrator": "orchestrator",
                "kubernetes": "kubernetes_agent",
                "jenkins": "jenkins_agent",
                "summarizer": "intelligent_summarizer"
            }
        )
        
        workflow.add_conditional_edges(
            "kubernetes_agent",
            self.router.post_kubernetes_routing_fixed,
            {
                "orchestrator": "orchestrator",
                "github": "github_agent",
                "summarizer": "intelligent_summarizer"
            }
        )
        
        workflow.add_conditional_edges(
            "jenkins_agent",
            self.router.post_jenkins_routing_fixed,
            {
                "orchestrator": "orchestrator",
                "kubernetes": "kubernetes_agent",
                "summarizer": "intelligent_summarizer"
            }
        )
        
        # Summarizer ends
        workflow.add_edge("intelligent_summarizer", END)
        workflow.add_edge("unavailable_agent", END)
        return workflow.compile()
    