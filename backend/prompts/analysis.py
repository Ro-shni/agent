ERROR_ANALYSIS_PROMPT = """
Analyze this error and provide helpful debugging information:

Error Details:
{error_message}

Context:
{error_context}

Please provide:
1. **Error Classification** - Type and category of error
2. **Possible Causes** - Likely reasons for the error
3. **Debugging Steps** - Specific actions to investigate
4. **Resolution Strategies** - Ways to fix the issue
5. **Prevention Tips** - How to avoid similar errors

Format your response with clear, actionable debugging guidance.
"""

# =============================================================================
# UTILITY PROMPTS
# =============================================================================

URL_ANALYSIS_PROMPT = """
Analyze this URL and determine what type of DevOps resource it represents:

URL: {url}

Classify as one of:
- github: GitHub repository, PR, or issue URL
- kubernetes: ArgoCD, Kubernetes dashboard, or cluster URL
- jenkins: Jenkins build, job, or pipeline URL
- unknown: Not a recognized DevOps resource

Provide reasoning for your classification.
"""

HEALTH_CHECK_PROMPT = """
Perform a health check on this DevOps resource:

Resource Type: {resource_type}
Resource URL: {resource_url}
Resource Status: {resource_status}

Provide:
1. **Health Status** - Overall health assessment
2. **Key Metrics** - Important performance indicators
3. **Issues Found** - Any problems or concerns
4. **Recommendations** - Actions to improve health
5. **Next Steps** - Immediate actions needed

Format your response with clear health indicators and actionable recommendations.
"""

