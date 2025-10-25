"""
The core orchestration engine for the Kairos multi-agent system.
"""
from typing import Dict, Any

from .correlation import IntelligentCorrelationEngine
from ..models.workflow import DevOpsWorkflowState
from ..utils.confidence_detector import ConfidenceDetector

from .workflow import WorkflowManager
from .service_manager import ServiceManager
from ..agents import GitHubAgent, JenkinsAgent
from .summarizer import Summarizer
from .node import Nodes

class UnifiedDevOpsOrchestrator:
    """COMPLETELY FIXED Production-ready Unified DevOps Orchestrator WITH INTELLIGENT CORRELATION"""
    
    def __init__(self):
        # 1. Initialize core services (LLM, tools, etc.)
        self.services = ServiceManager()
        
        # 2. Initialize agents that depend on services (will be updated after services are initialized)
        self.github_agent = None
        self.jenkins_agent = None
        self.summarizer = Summarizer()

        # 3. Initialize the nodes class, giving it access to the orchestrator instance
        #    so it can use the services and agents.
        self.nodes = Nodes(self)
        
        # 4. Initialize the workflow manager, giving it the nodes to build the graph.
        self.workflow_manager = WorkflowManager(self.nodes)
        self.correlation_engine = None
        self.rag_service = None

        self.initialized = False
        
    async def initialize(self) -> bool:
        """Initialize all tools and agents"""
        try:
            print("🚀 Initializing Unified DevOps Orchestrator with Intelligent Correlation...")
            
            # Initialize GitHub tools
            # await self._initialize_github_tools()
            
            # Initialize Kubernetes tools with WORKING pattern
            # await self._initialize_kubernetes_tools()
            
            # Initialize Kubernetes debugger
            # self.k8s_debugger = PerfectedKubernetesDebugger(self.kubernetes_tools, self.tool_logger, self.llm)
            
            # NEW: Initialize correlation engine
            # self.correlation_engine = IntelligentCorrelationEngine(self.llm)
            
            # NEW: Initialize RAG service for historical solutions
            # await self._initialize_rag_service()
            
            # Build the workflow
            # self.workflow_app = self._build_workflow()
            await self.services.initialize_all()
            # self.correlation_engine = IntelligentCorrelationEngine(self.services.llm)
            
            # Set the services from the service manager
            self.rag_service = self.services.rag_service
            self.mysql_service = self.services.mysql_service
            self.github_tools = self.services.github_tools
            self.kubernetes_tools = self.services.kubernetes_tools
            self.correlation_engine = self.services.correlation_engine
            
            # Initialize agents with RAG service
            self.github_agent = GitHubAgent(self.services.llm, self.services.tool_logger, self.rag_service)
            self.jenkins_agent = JenkinsAgent(self.services.llm, self.services.tool_logger, self.rag_service)
            
            self.initialized = True
            print("✅ Unified DevOps Orchestrator with Intelligent Correlation initialized successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Orchestrator initialization failed: {str(e)}")
            return False
        # Fix lines 1503-1550 in _initialize_kubernetes_tools method:
    # =================== WORKFLOW NODES ===================
   
    async def execute(self, user_prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute the complete intelligent workflow"""
        print(f"🔄 Executing intelligent workflow with user input: {user_prompt}")
        
        if not self.initialized:
            await self.initialize()
        
        print(f"\n🎯 STARTING INTELLIGENT DEVOPS ANALYSIS WITH CORRELATION")
        print("=" * 80)
        print(f"📋 Request: {user_prompt}")
        print("=" * 80)
        
        # Initialize state
        initial_state = DevOpsWorkflowState(
            user_prompt=user_prompt,
            context=context or {},
            task_analysis=None,
            github_response=None,
            kubernetes_response=None,
            jenkins_response=None,
            correlation_analysis=None,  # NEW
            historical_solutions=None,  # NEW
            routing_decisions=[],
            agent_memory={},
            execution_history=[],
            agent_status={},
            summary="",
            action_items=[],
            status="running",
            errors_found=[],
            confidence=None,
            confidence_level=None,
            confidence_reasoning=None,
            final_response=None
        )
        
        try:
            print("🔄 Executing intelligent multi-agent workflow with correlation...")
            
            # Execute workflow with higher recursion limit for dynamic routing
            final_state = await self.workflow_manager.workflow_app.ainvoke(initial_state, config={"recursion_limit": 15})
            
            print("\n" + "=" * 80)
            print("📊 INTELLIGENT DEVOPS CORRELATION ANALYSIS COMPLETE")
            print("=" * 80)
            print(final_state["summary"])
            print("=" * 80)
            
            # Confidence detection will be handled by the main API endpoint
            
            return final_state
            
        except Exception as e:
            print(f"❌ Intelligent workflow execution failed: {str(e)}")
            
            return {
                "status": "failed",
                "summary": f"Intelligent analysis failed: {str(e)}",
                "errors_found": [{"source": "workflow", "error": str(e)}]
            }
    
    def cleanup(self):
        """Cleanup resources"""
        if self.rag_service:
            self.rag_service.close()

