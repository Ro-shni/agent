from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class DevOpsQueryRequest(BaseModel):
    """Request model for DevOps analysis API"""
    query: str = Field(..., description="The DevOps query to analyze")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context for the analysis")
