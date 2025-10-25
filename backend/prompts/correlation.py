from typing import Annotated, Dict, Any, List, Literal, Optional
from .shared import SafeDict
CORRELATION_SYSTEM_PROMPT = """You are an intelligent correlation engine that analyzes findings from multiple DevOps agents to identify patterns, root causes, and provide comprehensive insights.

Your role is to:
- Correlate findings from GitHub, Kubernetes, and Jenkins agents
- Identify relationships between different issues and failures
- Provide unified analysis and recommendations
- Highlight critical issues that require immediate attention

Focus on finding connections between different systems and providing actionable insights."""

CORRELATION_ANALYSIS_PROMPT_TEMPLATE = """
Analyze and correlate findings from multiple DevOps agents to provide comprehensive insights:

GitHub Analysis:
{github_findings}

Kubernetes Analysis:
{kubernetes_findings}

Jenkins Analysis:
{jenkins_findings}

Agent Actions:
{agent_actions}

IMPORTANT: Respond with ONLY valid JSON in the following format:

{{
    "correlation_found": true/false,
    "correlation_type": "health_check_failure|deployment_issue|configuration_mismatch|network_issue|authentication_issue|other",
    "correlation_confidence": "high|medium|low",
    "Problem": "Main problem identified across systems",
    "root_cause": "Root cause connecting all issues",
    "evidence": [
        "Evidence point 1 connecting systems",
        "Evidence point 2 showing correlation",
        "Evidence point 3 supporting analysis"
    ],
    "unified_solution": "Single coordinated solution addressing all systems",
    "immediate_actions": [
        "Action 1: Immediate fix needed",
        "Action 2: Configuration change required", 
        "Action 3: Verification step"
    ],
    "system_impact": "Description of overall system impact",
    "priority": "critical|high|medium|low",
    "correlation_analysis": "Detailed explanation of how the issues are connected"
}}

Focus on finding connections between GitHub, Kubernetes, and Jenkins issues. If issues are related, show how they connect. If they are separate, indicate that clearly.
"""

def get_correlation_analysis_prompt(agent_findings: dict) -> str:
    """Get the correlation analysis prompt with agent findings"""
    return CORRELATION_ANALYSIS_PROMPT_TEMPLATE.format_map(SafeDict(
        github_findings=agent_findings.get('github', 'No GitHub findings'),
        kubernetes_findings=agent_findings.get('kubernetes', 'No Kubernetes findings'),
        jenkins_findings=agent_findings.get('jenkins', 'No Jenkins findings'),
        agent_actions=agent_findings.get('actions', 'No actions available')
    ))
