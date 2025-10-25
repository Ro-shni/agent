"""
Manages the initialization of all external services and tools,
such as LLMs, MCP clients, and agents.
"""
import asyncio
import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from ..config.settings import Settings
from ..agents.kubernetes_agent import PerfectedKubernetesDebugger
from ..utils.logging import ToolCallLogger
from ..utils.sql_service import mysql_service
from ..utils.rag_service import rag_service
from ..utils.detectors import namespace_detector
from .correlation import IntelligentCorrelationEngine

# Load environment variables
load_dotenv()
class ServiceManager:
    """Handles the setup and initialization of external services."""

    def __init__(self):
        self.llm = self._initialize_llm()
        self.tool_logger = ToolCallLogger()
        self.github_tools = []
        self.kubernetes_tools = []
        self.kubernetes_debugger = None
        self.correlation_engine = None
        self.mysql_service = None
        self.rag_service = None
        self.namespace_detector = None

    def _initialize_llm(self) -> AzureChatOpenAI:
        """Initialize Azure OpenAI LLM"""
        azure_config = Settings.get_azure_config()
        return AzureChatOpenAI(**azure_config)
    
    async def initialize_github_tools(self):
        """Initialize GitHub MCP tools"""
        try:
            print("🔄 Initializing GitHub MCP tools...")
            github_config = Settings.get_github_config()
            print("github_config")
            print(github_config)
            client = MultiServerMCPClient({
                "github": {
                    "url": github_config["mcp_url"],
                    "transport": "streamable_http",
                    "headers": {
                        "Authorization": f"Bearer {github_config['token']}"
                    }
                }
            })
            
            all_tools = await client.get_tools()
            
            target_tool_names = [
                "get_pull_request_status",
                "get_pull_request_comments", 
                "get_pull_request_reviews",
                "get_pull_request",
                "get_issue_comments",
                "list_workflow_runs",
                "get_workflow_run",
                "list_workflow_jobs"
            ]
            
            self.github_tools = [tool for tool in all_tools if tool.name in target_tool_names]
            print(f"✅ GitHub agent initialized with {len(self.github_tools)} tools")
            
        except Exception as e:
            print(f"❌ GitHub tools initialization failed: {str(e)}")
            self.github_tools = []
    
    async def initialize_kubernetes_tools(self):
        """Initialize Kubernetes MCP tools using WORKING pattern with timeout"""
        try:
            print("🔄 Loading Kubernetes MCP tools...")
            
            # Add timeout wrapper
            import asyncio
            
            async def init_k8s_client():
                client = MultiServerMCPClient({
                    "kubernetes": {
                        "transport": "stdio",
                        "command": "npx",
                        "args": ["-y", "kubernetes-mcp-server@latest", "--list-output", "yaml"]
                    }
                })
                print("✅ K8s MCP client created")
                
                # Get tools with timeout
                all_tools = await client.get_tools()
                print(f"✅ Retrieved {len(all_tools)} tools")
                return client, all_tools
            
            # Use timeout to prevent hanging
            try:
                client, all_tools = await asyncio.wait_for(init_k8s_client(), timeout=30.0)
            except asyncio.TimeoutError:
                print("❌ Kubernetes MCP client initialization timed out (30s)")
                print("⚠️ Continuing without Kubernetes tools - system will work in degraded mode")
                self.kubernetes_tools = []
                return
            
            # Use the exact tool names that work
            target_tool_names = [
                "configuration_view",
                "events_list", 
                "namespaces_list",
                "pods_get",
                "pods_list_in_namespace",
                "pods_log",
                "pods_top",
                "resources_get",
                "resources_list"
            ]
            
            self.kubernetes_tools = []
            for tool in all_tools:
                if tool.name in target_tool_names:
                    self.kubernetes_tools.append(tool)
                    print(f"✅ Found: {tool.name}")
            
            print(f"✅ Kubernetes tools loaded: {len(self.kubernetes_tools)}")
            
            # Initialize debugger with LLM and RAG service (will be set after RAG service is initialized)
            self.kubernetes_debugger = None
                
        except Exception as e:
            print(f"❌ Failed to initialize Kubernetes tools: {str(e)}")
            print("⚠️ Continuing without Kubernetes tools - system will work in degraded mode")
            self.kubernetes_tools = []
            self.kubernetes_debugger = None
    
    # async def initialize_rag_service(self):
    #     """Initialize MongoDB RAG service for historical solutions"""
    #     try:
    #         print("🔄 Initializing MongoDB RAG Service...")
            
    #         # Get MongoDB config with fallback values
    #         mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    #         mongo_database = os.getenv("MONGO_DATABASE", "dev-ops-buddy")
    #         mongo_collection = os.getenv("MONGO_COLLECTION", "JiraIssues")
    #         mongo_timeout = int(os.getenv("MONGO_TIMEOUT", "30"))
            
    #         self.rag_service = MongoDBRAGService(
    #             mongo_uri=mongo_uri,
    #             database=mongo_database,
    #             collection=mongo_collection,
    #             timeout=mongo_timeout
    #         )
            
    #         success = await self.rag_service.initialize()
    #         if success:
    #             print("✅ MongoDB RAG Service initialized successfully!")
    #         else:
    #             print("⚠️ MongoDB RAG Service initialization failed - continuing without historical solutions")
    #             self.rag_service = None
                
    #     except Exception as e:
    #         print(f"❌ RAG Service initialization failed: {str(e)}")
    #         print("⚠️ Continuing without historical solutions - system will work normally")
    #         self.rag_service = None
    
    async def intiializeCorrelationEngine(self):
        """Initialize Correlation Engine"""
        self.correlation_engine = IntelligentCorrelationEngine(self.llm)
    
    async def initialize_mysql_service(self):
        """Initialize MySQL service for service details"""
        try:
            print("🔄 Initializing MySQL service...")
            success = await mysql_service.initialize()
            if success:
                self.mysql_service = mysql_service
                print("✅ MySQL service initialized successfully!")
            else:
                print("⚠️ MySQL service initialization failed - continuing without service mapping")
            return success
        except Exception as e:
            print(f"❌ MySQL service initialization failed: {str(e)}")
            return False
    
    async def initialize_rag_service(self):
        """Initialize RAG service for historical solutions"""
        try:
            print("🔄 Initializing RAG service...")
            success = await rag_service.initialize()
            if success:
                self.rag_service = rag_service
                print("✅ RAG service initialized successfully!")
            else:
                print("⚠️ RAG service initialization failed - continuing without historical solutions")
            return success
        except Exception as e:
            print(f"❌ RAG service initialization failed: {str(e)}")
            return False
    
    async def initialize_namespace_detector(self):
        """Initialize namespace detector"""
        try:
            print("🔄 Initializing namespace detector...")
            self.namespace_detector = namespace_detector
            print("✅ Namespace detector initialized successfully!")
            return True
        except Exception as e:
            print(f"❌ Namespace detector initialization failed: {str(e)}")
            return False
    
    async def initialize_all(self):
        """Initialize all services"""
        
        await self.initialize_github_tools()
        await self.initialize_kubernetes_tools()
        await self.intiializeCorrelationEngine()
        await self.initialize_mysql_service()
        await self.initialize_rag_service()
        await self.initialize_namespace_detector()
        
        # Initialize Kubernetes debugger with RAG service now that it's available
        await self.initialize_kubernetes_debugger()
    
    async def initialize_kubernetes_debugger(self):
        """Initialize Kubernetes debugger with RAG service"""
        try:
            if self.kubernetes_tools and self.llm:
                self.kubernetes_debugger = PerfectedKubernetesDebugger(
                    self.kubernetes_tools, 
                    self.tool_logger,
                    self.llm,
                    self.rag_service
                )
                print("✅ Kubernetes debugger initialized with RAG service")
            else:
                print("⚠️ Kubernetes tools or LLM not available - skipping debugger initialization")
        except Exception as e:
            print(f"❌ Kubernetes debugger initialization failed: {str(e)}")
            self.kubernetes_debugger = None

