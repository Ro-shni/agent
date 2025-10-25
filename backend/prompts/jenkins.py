from .shared import SafeDict
from typing import Annotated, Dict, Any, List, Literal, Optional

JENKINS_SYSTEM_PROMPT = """You are an expert CI/CD analyst specializing in Jenkins build failure analysis and pipeline debugging.

Your expertise includes:
- Analyzing build logs and identifying root causes
- Troubleshooting compilation, test, and deployment failures
- Providing specific remediation steps and best practices
- Optimizing CI/CD pipeline performance and reliability

CRITICAL: You must respond with a JSON object containing exactly these fields:
- problem_identified: A clear, concise description of what went wrong
- root_cause: The specific technical reason for the failure
- solution: Step-by-step actions to fix the issue
- summary: A brief overview of the problem and resolution

Format your response as valid JSON only, no additional text."""

JENKINS_ANALYSIS_PROMPT_TEMPLATE = """
Analyze this Jenkins build failure and provide a structured response:

Build Information:
- Environment: {environment}
- Job Path: {job_path}
- Build Number: {build_number}
- Status: {build_status}
- Duration: {build_duration}ms
- Timestamp: {build_timestamp}

Build Logs (last 300 lines):
{build_logs}

Respond with a JSON object containing exactly these fields:
{{
    "problem_identified": "Clear description of what went wrong",
    "root_cause": "Specific technical reason for the failure",
    "solution": "Step-by-step actions to fix the issue",
    "summary": "Brief overview of the problem and resolution"
}}

Provide specific technical details and actionable recommendations.
"""

def get_jenkins_analysis_prompt(build_data: dict) -> str:
    """Get the Jenkins analysis prompt with build data"""
    return JENKINS_ANALYSIS_PROMPT_TEMPLATE.format_map(SafeDict(
        environment=build_data.get('environment', 'unknown'),
        job_path=build_data.get('job_path', 'unknown'),
        build_number=build_data.get('build_number', 'unknown'),
        build_status=build_data.get('build_status', 'unknown'),
        build_duration=build_data.get('build_duration', 0),
        build_timestamp=build_data.get('build_timestamp', 'unknown'),
        build_logs=build_data.get('build_logs', 'No logs available')
    ))
