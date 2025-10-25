"""
Kairos: Unified DevOps Multi-Agent System
Advanced AI-powered DevOps orchestration and analysis platform
"""
__version__ = "1.0.0"
__author__ = "DevOps Team"

from .main import main
from .app import app
from .core.orchestrator import UnifiedDevOpsOrchestrator

__all__ = ["main", "app", "UnifiedDevOpsOrchestrator"]