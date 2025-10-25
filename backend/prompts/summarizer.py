from .shared import SafeDict
from typing import Annotated, Dict, Any, List, Literal, Optional

INTELLIGENT_SUMMARIZER_PROMPT = """
You are a DevOps expert providing actionable analysis to developers. 

**Available Findings:**
GitHub Analysis: {github_findings}
Kubernetes Analysis: {kubernetes_findings}
Jenkins Analysis: {jenkins_findings}

**Your Task:**
{analysis_mode}

**Response Format:**
Provide a concise, developer-focused summary with:

1. **Problem Summary** (2-3 sentences max)
2. **Root Cause** (specific technical issue)  
3. **Developer Actions** (concrete steps to fix)
4. **Verification** (how to confirm the fix worked)

Keep it practical and actionable. Avoid generic advice.
"""

FINAL_RESPONSE_SYSTEM_PROMPT = """You are a senior DevOps expert who synthesizes analysis from multiple agents to provide the definitive final response.

**Your Task:**
Analyze ALL the available findings and generate a single, definitive JSON response that represents the most accurate and complete understanding of the situation.

**Rules:**
1. If correlation analysis found connections between systems, prioritize that unified view
2. If only one agent has findings, focus on those findings but consider context from others
3. If multiple agents have independent findings, synthesize them intelligently
4. Be specific and actionable - avoid generic responses.
5. DO NOT mention historical data or historical solutions
6. Focus ONLY on current analysis and evidence-based root causes

**Required JSON Format:**
{{
    "status": "success|failed|issues_found",
    "problem_identified": "Clear, specific description of the main problem",
    "root_cause": "Technical root cause based on all available evidence",
    "solution": ["Specific action 1", "Specific action 2", "Specific action 3"],
    "summary": "Brief overview of the complete analysis and recommended approach"
}}

Respond with ONLY the JSON object, no additional text."""

FINAL_RESPONSE_USER_PROMPT_TEMPLATE = """
**Available Analysis:**

GitHub Findings: {github_findings}

Kubernetes Findings: {kubernetes_findings}

Jenkins Findings: {jenkins_findings}

Correlation Analysis: {correlation_analysis}

Historical Solutions: {historical_solutions}

Recommended Actions: {all_actions}
"""

def get_analysis_mode(github_findings, kubernetes_findings, jenkins_findings):
    """Determine what type of analysis to perform"""
    active_agents = []
    if github_findings: active_agents.append("GitHub")
    if kubernetes_findings: active_agents.append("Kubernetes") 
    if jenkins_findings: active_agents.append("Jenkins")
    
    if len(active_agents) > 1:
        return f"Correlate findings from {', '.join(active_agents)} to identify relationships and provide unified recommendations."
    elif len(active_agents) == 1:
        return f"Analyze the {active_agents[0]} findings and provide actionable recommendations for developers."
    else:
        return "Analyze available findings and provide general troubleshooting recommendations."

def get_intelligent_summarizer_prompt(github_findings, kubernetes_findings, jenkins_findings):
    """Get the intelligent summarizer prompt with adaptive analysis mode"""
    analysis_mode = get_analysis_mode(github_findings, kubernetes_findings, jenkins_findings)
    return INTELLIGENT_SUMMARIZER_PROMPT.format_map(SafeDict(
        github_findings=github_findings or "No GitHub analysis performed",
        kubernetes_findings=kubernetes_findings or "No Kubernetes analysis performed", 
        jenkins_findings=jenkins_findings or "No Jenkins analysis performed",
        analysis_mode=analysis_mode
    ))