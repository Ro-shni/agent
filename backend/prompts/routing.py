
# =============================================================================
# POST-AGENT ROUTING PROMPTS
# =============================================================================

POST_GITHUB_ROUTING_PROMPT = """
Based on the GitHub analysis findings, determine if additional analysis is needed:

GitHub Findings:
{github_findings}

Consider:
- Are there CI/CD failures that might affect deployment?
- Are there infrastructure or deployment-related issues mentioned?
- Would Kubernetes analysis help understand the impact?

Route to:
- kubernetes: If there are CI/CD failures or deployment issues
- summarizer: If analysis is complete and no additional agents needed
"""

POST_JENKINS_ROUTING_PROMPT = """
Based on the Jenkins analysis findings, determine if additional analysis is needed:

Jenkins Findings:
{jenkins_findings}

Consider:
- Are there build failures that might affect deployment?
- Are there infrastructure issues that need Kubernetes analysis?
- Would additional analysis help understand the impact?

Route to:
- kubernetes: If there are build failures affecting deployment
- summarizer: If analysis is complete and no additional agents needed
"""

POST_KUBERNETES_ROUTING_PROMPT = """
Based on the Kubernetes analysis findings, determine if additional analysis is needed:

Kubernetes Findings:
{kubernetes_findings}

Consider:
- Are there issues that might be related to code changes?
- Are there deployment issues that need GitHub analysis?
- Would additional analysis help understand the root cause?

Route to:
- github: If there are code-related issues or deployment problems
- summarizer: If analysis is complete and no additional agents needed
"""
