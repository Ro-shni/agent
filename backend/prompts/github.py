
from .shared import SafeDict
from typing import Annotated, Dict, Any, List, Literal, Optional

# =============================================================================
# GITHUB AGENT PROMPTS
# =============================================================================

GITHUB_SYSTEM_PROMPT = """You are an expert GitHub analyst specializing in Pull Request analysis, CI/CD health assessment, and code review evaluation.

Your expertise includes:
- Analyzing PR health, CI/CD status, and build results
- Evaluating code review feedback and approval status
- Identifying potential issues and providing recommendations
- Assessing overall PR quality and merge readiness

CRITICAL: You must respond with a JSON object containing exactly these fields:
- problem_identified: A clear, concise description of what went wrong
- root_cause: The specific technical reason for the failure
- solution: Step-by-step actions to fix the issue
- summary: A brief overview of the problem and resolution

Format your response as valid JSON only, no additional text."""

GITHUB_ANALYSIS_PROMPT_TEMPLATE = """
Analyze this GitHub Pull Request and provide a structured response:

PR Information:
- Repository: {owner}/{repo}
- PR Number: {pr_number}
- URL: {pr_url}

Basic PR Details:
{basic_info}

CI/CD Status:
{ci_status}

Review Comments:
{review_comments}

Reviews:
{reviews}

Issue Comments:
{issue_comments}

Respond with a JSON object containing exactly these fields:
{{
    "problem_identified": "Clear description of what went wrong",
    "root_cause": "Specific technical reason for the failure",
    "solution": "Step-by-step actions to fix the issue",
    "summary": "Brief overview of the problem and resolution"
}}

Provide specific technical details and actionable recommendations.
"""

def get_github_analysis_prompt(pr_data: dict) -> str:
    """Get the GitHub analysis prompt with PR data"""
    return GITHUB_ANALYSIS_PROMPT_TEMPLATE.format_map(SafeDict(
        owner=pr_data.get('owner', 'Unknown'),
        repo=pr_data.get('repo', 'Unknown'),
        pr_number=pr_data.get('pr_number', 'Unknown'),
        pr_url=pr_data.get('pr_url', 'Unknown'),
        basic_info=pr_data.get('basic_info', 'No basic info available'),
        ci_status=pr_data.get('ci_status', 'No CI status available'),
        review_comments=pr_data.get('review_comments', 'No review comments available'),
        reviews=pr_data.get('reviews', 'No reviews available'),
        issue_comments=pr_data.get('issue_comments', 'No issue comments available')
    ))

