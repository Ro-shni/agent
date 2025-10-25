# Kairos/app.py
"""
FastAPI application for Kairos API endpoints
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import asyncio

from .models.requests import DevOpsQueryRequest
from .models.responses import DevOpsQueryResponse
from .core.orchestrator import UnifiedDevOpsOrchestrator
from .utils.confidence_detector import ConfidenceDetector
import time
from contextlib import asynccontextmanager

# Global orchestrator instance
orchestrator_instance = None
orchestrator_initialized = False
orchestrator_error = None
from dotenv import load_dotenv
load_dotenv()
async def initialize_orchestrator():
    """Initialize the orchestrator instance"""
    global orchestrator_instance
    global orchestrator_initialized
    global orchestrator_error
    if orchestrator_instance is None:
        try:
            orchestrator_instance = UnifiedDevOpsOrchestrator()
            await orchestrator_instance.initialize()
            orchestrator_initialized = True
        except Exception as e:
            orchestrator_error = str(e)
            raise
    return orchestrator_instance

async def get_orchestrator():
    """Get the global orchestrator instance (non-blocking)"""
    global orchestrator_instance
    if orchestrator_instance is None:
        raise HTTPException(
            status_code=503, 
            detail="Orchestrator not initialized yet. Please wait for startup to complete."
        )
    return orchestrator_instance

# Create FastAPI app


# @app.on_event("startup")
# async def startup_event():
#     """Initialize orchestrator on startup"""
#     print("🚀 Starting DevOps Analysis API...")
#     await initialize_orchestrator()
#     print("✅ DevOps Analysis API ready!")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting DevOps Analysis API...")
    await initialize_orchestrator()
    print("✅ DevOps Analysis API ready!")
    yield
    print("Shutting down DevOps Analysis API...")
    print("Cleaning up resources...")
    # Add any cleanup code here if needed
    global orchestrator_instance
    if orchestrator_instance and hasattr(orchestrator_instance, 'cleanup'):
        try:
            orchestrator_instance.cleanup()
        except Exception as e:
            print(f"⚠️ Error during cleanup: {e}")
    
    print("✅ DevOps Analysis API shutdown complete!")

    print("DevOps Analysis API shutdown complete!")


app = FastAPI(
    title="DevOps Analysis API",
    description="Unified DevOps Multi-Agent Analysis System with Intelligent Correlation",
    version="1.0.0",
    lifespan=lifespan
)
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DevOps Analysis API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "analyze": "/analyze - POST endpoint for DevOps analysis",
            "analyze_github": "/analyze/github - POST endpoint for GitHub-only analysis",
            "analyze_kubernetes": "/analyze/kubernetes - POST endpoint for Kubernetes-only analysis",
            "analyze_jenkins": "/analyze/jenkins - POST endpoint for Jenkins-only analysis",
            "health": "/health - Health check endpoint",
            "docs": "/docs - API documentation"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        orchestrator = await get_orchestrator()
        return {
            "status": "healthy",
            "orchestrator_initialized": orchestrator.initialized,
            "github_tools": len(orchestrator.github_tools) if hasattr(orchestrator, 'github_tools') else 0,
            "kubernetes_tools": len(orchestrator.kubernetes_tools) if hasattr(orchestrator, 'kubernetes_tools') else 0,
            "jenkins_agent": hasattr(orchestrator, 'jenkins_agent') and orchestrator.jenkins_agent is not None
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.post("/analyzeold")
async def analyze_devops_query(request: DevOpsQueryRequest):
    """Main API endpoint for DevOps analysis - returns standardized format"""
    # Simple confidence detection will be done after orchestrator execution
    
    try:
        # Initialize orchestrator if not already done
        orchestrator = await get_orchestrator()
        
        if not orchestrator.initialized:
            raise HTTPException(status_code=500, detail="Orchestrator services not fully initialized")
        
        print(f"🔍 API Request: {request.query}")
        
        # Execute the analysis
        result = await orchestrator.execute(
            user_prompt=request.query,
            context=request.context or {}
        )
        
        # Extract analysis results
        github_response = result.get("github_response")
        kubernetes_response = result.get("kubernetes_response")
        jenkins_response = result.get("jenkins_response")
        historical_solutions = result.get("historical_solutions")
        
        # Simple confidence detection: check if any agents were actually used
        confidence = False
        confidence_level = "low"
        confidence_reasoning = "No agents were used for this query"
        
        # Check if any agent provided meaningful analysis
        if result.get("unavailable_response"):
            confidence = False
            confidence_level = "low"
            confidence_reasoning = "Request does not require DevOps analysis"
        elif kubernetes_response and hasattr(kubernetes_response, 'findings') and kubernetes_response.findings:
            confidence = True
            confidence_level = "high"
            confidence_reasoning = "Kubernetes agent provided analysis for this query"
        elif github_response and hasattr(github_response, 'findings') and github_response.findings:
            confidence = True
            confidence_level = "high"
            confidence_reasoning = "GitHub agent provided analysis for this query"
        elif jenkins_response and hasattr(jenkins_response, 'findings') and jenkins_response.findings:
            confidence = True
            confidence_level = "high"
            confidence_reasoning = "Jenkins agent provided analysis for this query"
        else:
            confidence = False
            confidence_level = "low"
            confidence_reasoning = "No agents were used for this query"
        
        print(f"🔍 Confidence Detection: {confidence} ({confidence_level}) - {confidence_reasoning}")
        print(f"🔍 Agent responses: github={bool(github_response)}, jenkins={bool(jenkins_response)}, kubernetes={bool(kubernetes_response)}")
        
        # Determine which agent provided the primary analysis
        primary_analysis = None
        if jenkins_response and hasattr(jenkins_response, 'findings') and jenkins_response.findings:
            primary_analysis = jenkins_response.findings
        elif kubernetes_response and hasattr(kubernetes_response, 'findings') and kubernetes_response.findings:
            primary_analysis = kubernetes_response.findings
        elif github_response and hasattr(github_response, 'findings') and github_response.findings:
            primary_analysis = github_response.findings
        
        # If we have a primary analysis from an agent, use it directly
        if primary_analysis:
            standardized_result = {
                "status": primary_analysis.get("status", "success"),
                "problem_identified": primary_analysis.get("problem_identified", "Unknown problem"),
                "root_cause": primary_analysis.get("root_cause", "Unknown root cause"),
                "solution": primary_analysis.get("solution", ["No solution provided"]),
                "summary": primary_analysis.get("summary", "No summary available"),
                "rag_solution": primary_analysis.get("rag_solution", {
                    "rag_solution": None,
                    "similarity_score": 0.0,
                    "jira_id": None,
                    "message": "No RAG solution available"
                }),
                "confidence": confidence,
                "confidence_level": confidence_level,
                "confidence_reasoning": confidence_reasoning
            }
        else:
            # Fallback to historical solutions if no agent analysis
            rag_solution = {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "No RAG solution available"
            }
            
            if historical_solutions and historical_solutions.get("solutions"):
                solutions = historical_solutions["solutions"]
                if solutions and len(solutions) > 0:
                    top_solution = solutions[0]
                    rag_solution = {
                        "rag_solution": top_solution.get("solution", "No solution available"),
                        "similarity_score": top_solution.get("similarity", 0.0),
                        "jira_id": top_solution.get("jira_id", "Unknown"),
                        "message": f"Found relevant solution from JIRA {top_solution.get('jira_id', 'Unknown')} (Similarity: {top_solution.get('similarity', 0.0):.1f}%)"
                    }
            
            standardized_result = {
                "status": result.get("status", "success"),
                "problem_identified": "No specific problem identified",
                "root_cause": "Root cause not determined",
                "solution": ["No solution available"],
                "summary": result.get("summary", "No summary available"),
                "rag_solution": rag_solution,
                "confidence": confidence,
                "confidence_level": confidence_level,
                "confidence_reasoning": confidence_reasoning
            }
        
        print(f"✅ API Response: {standardized_result['status']}")
        return standardized_result
        
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        
        # Simple confidence detection for error case
        confidence = False
        confidence_level = "low"
        confidence_reasoning = "Analysis failed - no agents could be used"
        
        # Check if query looks like it should use agents
        query_lower = request.query.lower()
        if any(keyword in query_lower for keyword in ["jenkins", "github", "kubernetes", "k8s", "pod", "namespace", "build", "ci/cd", "pr", "pull request"]):
            confidence = True
            confidence_level = "medium"
            confidence_reasoning = "Query appears to be DevOps-related but analysis failed"
        
        return {
            "status": "failed",
            "problem_identified": "No specific problem identified",
            "root_cause": "Root cause not determined",
            "solution": ["No solution available"],
            "summary": f"Intelligent analysis failed: {str(e)}",
            "rag_solution": {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "No RAG solution available"
            },
            "confidence": confidence,
            "confidence_level": confidence_level,
            "confidence_reasoning": confidence_reasoning
        }

@app.post("/analyze")
async def analyze_devops_query(request: DevOpsQueryRequest):
    """Main API endpoint for DevOps analysis - returns standardized format from workflow"""
    
    try:
        # Initialize orchestrator if not already done
        orchestrator = await get_orchestrator()
        
        if not orchestrator.initialized:
            raise HTTPException(status_code=500, detail="Orchestrator services not fully initialized")
        
        print(f"🔍 API Request: {request.query}")
        
        # Execute the analysis workflow
        result = await orchestrator.execute(
            user_prompt=request.query,
            context=request.context or {}
        )
        
        # CRITICAL: The workflow nodes are responsible for generating the final_response
        print(f"🔍 Result: {result}")   
        final_response = result.get("final_response")
        if final_response.get("root_cause") == "Unknown root cause":
            final_response["confidence"] = False
            return final_response
        if final_response:
            print(f"✅ API Response from workflow: {final_response.get('status', 'unknown')}")
            print(f"🔍 Problem: {final_response.get('problem_identified', 'unknown')}")
            print(f"🔍 Confidence: {final_response.get('confidence_level', 'unknown')} ({final_response.get('confidence_reasoning', 'unknown')})")
            return final_response
        else:
            # This should never happen if the workflow is properly implemented
            print("❌ CRITICAL: No final_response found in workflow result - this is a workflow bug!")
            print(f"❌ Available keys in result: {list(result.keys())}")
            
            return {
                "status": "failed",
                "problem_identified": "Workflow execution error",
                "root_cause": "Workflow did not produce final_response - this is a system bug",
                "solution": ["Contact DevOps team - workflow malfunction", "Check workflow node implementations"],
                "summary": "Workflow execution failed to produce final response",
                "rag_solution": {
                    "rag_solution": None,
                    "similarity_score": 0.0,
                    "jira_id": None,
                    "message": "No RAG solution available due to workflow error"
                },
                "confidence": False,
                "confidence_level": "low",
                "confidence_reasoning": "Workflow execution failed to produce final response"
            }
        
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        
        return {
            "status": "failed",
            "problem_identified": "API execution error",
            "root_cause": f"API error: {str(e)}",
            "solution": ["Contact DevOps team for assistance", "Retry the request", "Check system logs"],
            "summary": f"API execution failed: {str(e)}",
            "rag_solution": {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "No RAG solution available due to API error"
            },
            "confidence": False,
            "confidence_level": "low",
            "confidence_reasoning": "API execution failed"
        }

@app.post("/analyze/github")
async def analyze_github_only(request: DevOpsQueryRequest):
    """GitHub-only analysis endpoint"""
    try:
        # orchestrator = await initialize_orchestrator()
        orchestrator = await get_orchestrator()

        if not orchestrator.initialized:
            raise HTTPException(status_code=500, detail="Orchestrator not initialized")
        
        # Use the GitHub agent directly
        github_agent = orchestrator.github_agent
        result = await github_agent.analyze(request.query)
        
        # Get confidence information
        confidence_info = ConfidenceDetector.detect_confidence(request.query)
        
        # Force return only standardized format with RAG solution
        standardized_result = {
            "status": result.get("status", "success"),
            "problem_identified": result.get("problem_identified", "Unknown problem"),
            "root_cause": result.get("root_cause", "Unknown root cause"),
            "solution": result.get("solution", "No solution provided"),
            "summary": result.get("summary", "No summary available"),
            "rag_solution": result.get("rag_solution", {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "No RAG solution available"
            }),
            "confidence": confidence_info["confidence"],
            "confidence_level": confidence_info["confidence_level"],
            "confidence_reasoning": confidence_info["reasoning"]
        }
        
        return standardized_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub analysis failed: {str(e)}")

@app.post("/analyze/kubernetes")
async def analyze_kubernetes_only(request: DevOpsQueryRequest):
    """Kubernetes-only analysis endpoint"""
    try:
        orchestrator = await get_orchestrator()

        if not orchestrator.initialized:
            raise HTTPException(status_code=500, detail="Orchestrator not initialized")
        
        # Use the Kubernetes agent directly
        k8s_agent = orchestrator.services.kubernetes_debugger
        
        # Extract namespace info from the query
        namespace_detector = orchestrator.services.namespace_detector
        namespace_info = await namespace_detector.extract_namespace_info_from_user_input(request.query)
        
        result = await k8s_agent.debug_application_health(
            namespace=namespace_info.get("namespaces", ["default"])[0],
            environment=namespace_info.get("environment", "stg"), 
            business_unit=namespace_info.get("business_unit", "supply")
        )
        
        # Get confidence information
        confidence_info = ConfidenceDetector.detect_confidence(request.query)
        
        # Force return only standardized format with RAG solution
        standardized_result = {
            "status": result.get("status", "success"),
            "problem_identified": result.get("problem_identified", "Unknown problem"),
            "root_cause": result.get("root_cause", "Unknown root cause"),
            "solution": result.get("solution", "No solution provided"),
            "summary": result.get("summary", "No summary available"),
            "rag_solution": result.get("rag_solution", {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "No RAG solution available"
            }),
            "confidence": confidence_info["confidence"],
            "confidence_level": confidence_info["confidence_level"],
            "confidence_reasoning": confidence_info["reasoning"]
        }
        
        return standardized_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kubernetes analysis failed: {str(e)}")

@app.post("/analyze/jenkins")
async def analyze_jenkins_only(request: DevOpsQueryRequest):
    """Jenkins-only analysis endpoint"""
    try:
        orchestrator = await get_orchestrator()

        if not orchestrator.initialized:
            raise HTTPException(status_code=500, detail="Orchestrator not initialized")
        
        # Use the Jenkins agent directly
        jenkins_agent = orchestrator.jenkins_agent
        result = await jenkins_agent.analyze(request.query)
        
        # Get confidence information
        confidence_info = ConfidenceDetector.detect_confidence(request.query)
        
        # Force return only standardized format with RAG solution
        standardized_result = {
            "status": result.get("status", "success"),
            "problem_identified": result.get("problem_identified", "Unknown problem"),
            "root_cause": result.get("root_cause", "Unknown root cause"),
            "solution": result.get("solution", "No solution provided"),
            "summary": result.get("summary", "No summary available"),
            "rag_solution": result.get("rag_solution", {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "No RAG solution available"
            }),
            "confidence": confidence_info["confidence"],
            "confidence_level": confidence_info["confidence_level"],
            "confidence_reasoning": confidence_info["reasoning"]
        }
        
        return standardized_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Jenkins analysis failed: {str(e)}")

def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI server"""
    print(f"🚀 Starting DevOps Analysis API server on {host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"🔍 Health Check: http://{host}:{port}/health")
    print(f"🎯 Analysis Endpoint: http://{host}:{port}/analyze")
    
    # Use uvicorn.run in a way that doesn't conflict with asyncio.run
    import threading
    import uvicorn
    
    def run_server():
        uvicorn.run(app, host=host, port=port, log_level="info")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Shutting down API server...")

