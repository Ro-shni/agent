from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class DevOpsQueryResponse(BaseModel):
    """Response model for DevOps analysis API"""
    status: str = Field(..., description="Analysis status")
    summary: str = Field(..., description="Analysis summary")
    action_items: List[str] = Field(..., description="Actionable recommendations")
    github_analysis: Optional[Dict[str, Any]] = Field(default=None, description="GitHub analysis results")
    kubernetes_analysis: Optional[Dict[str, Any]] = Field(default=None, description="Kubernetes analysis results")
    jenkins_analysis: Optional[Dict[str, Any]] = Field(default=None, description="Jenkins analysis results")
    correlation_analysis: Optional[Dict[str, Any]] = Field(default=None, description="Correlation analysis results")
    historical_solutions: Optional[Dict[str, Any]] = Field(default=None, description="Historical solutions from RAG")
    execution_path: List[Dict[str, Any]] = Field(..., description="Execution path taken")
    errors: List[Dict[str, Any]] = Field(default=[], description="Any errors encountered")

