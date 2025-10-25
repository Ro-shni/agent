"""
Intelligent Correlation Engine
Correlates findings between different DevOps domains (e.g., GitHub and Kubernetes)
to identify cross-cutting root causes.
"""
import json
from typing import Dict, Any

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Import centralized prompts from the new structure
from ..prompts.correlation import CORRELATION_SYSTEM_PROMPT,CORRELATION_ANALYSIS_PROMPT_TEMPLATE 


class IntelligentCorrelationEngine:
    """NEW: Correlates findings between GitHub and Kubernetes to identify root causes"""
    
    def __init__(self, llm: AzureChatOpenAI):
        self.llm = llm
    
    async def correlate_findings(self, github_findings: Dict[str, Any], k8s_findings: Dict[str, Any], jenkins_findings: Dict[str, Any], user_prompt: str) -> Dict[str, Any]:
        """Correlate GitHub and Kubernetes findings to identify root causes"""
        
        print("\n🧠 INTELLIGENT CORRELATION: Connecting GitHub + Kubernetes findings...")
        
        agent_findings = {
        "github": json.dumps(github_findings, indent=2) if github_findings else "No GitHub findings available",
        "kubernetes": json.dumps(k8s_findings, indent=2) if k8s_findings else "No Kubernetes findings available", 
        "jenkins": json.dumps(jenkins_findings, indent=2) if jenkins_findings else "No Jenkins findings available",
        "actions": f"Correlation analysis for user request: {user_prompt}"
    }

        # Use centralized correlation prompt
        # correlation_prompt = ChatPromptTemplate.from_template(
        #     CORRELATION_SYSTEM_PROMPT + "\n\n" + get_correlation_analysis_prompt({
        #         "github": "{github_findings}",
        #         "kubernetes": "{k8s_findings}",
        #         "jenkins": "{jenkins_findings}",
        #         "actions": "Correlation analysis for user request: {user_prompt}"
        #     })
        # )
        correlation_prompt = ChatPromptTemplate.from_template(
            CORRELATION_SYSTEM_PROMPT + "\n\n" + CORRELATION_ANALYSIS_PROMPT_TEMPLATE
        )



        
        try:
            correlation_chain = correlation_prompt | self.llm
            
            response = await correlation_chain.ainvoke({
                "user_prompt": user_prompt,
                "github_findings": agent_findings.get('github', 'No GitHub findings'),
                "kubernetes_findings": agent_findings.get('kubernetes', 'No Kubernetes findings'), 
                "jenkins_findings": agent_findings.get('jenkins', 'No Jenkins findings'),
                "agent_actions": agent_findings.get('actions', 'No actions available')
            })
            # Parse the correlation response
            content = response.content.strip()
            print(f"🔍 DEBUG: Raw LLM response: '{content[:200]}...'")  # Debug line

            if not content:
                print("⚠️ Empty response from LLM, using fallback")
                return self._fallback_correlation(github_findings, k8s_findings)
            

            # Clean JSON response
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            if not content or content == "":
                print("⚠️ Empty content after cleaning, using fallback")
                return self._fallback_correlation(github_findings, k8s_findings)

            try:
                correlation_result = json.loads(content)
            except json.JSONDecodeError as json_err:
                print(f"⚠️ JSON parsing failed: {str(json_err)}")
                print(f"🔍 Content that failed to parse: '{content[:500]}...'")
                return self._fallback_correlation(github_findings, k8s_findings)
            
            print(f"🧠 Correlation Result:")
            print(f"   • Found: {correlation_result.get('correlation_found', False)}")
            print(f"   • Type: {correlation_result.get('correlation_type', 'unknown')}")
            print(f"   • Confidence: {correlation_result.get('correlation_confidence', 'unknown')}")
                        
            return correlation_result
            
        except Exception as e:
            print(f"⚠️ Correlation analysis failed: {str(e)}")
            
            # Fallback: Simple pattern matching correlation
            return self._fallback_correlation(github_findings, k8s_findings)
    
    def _fallback_correlation(self, github_findings: Dict[str, Any], k8s_findings: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback correlation using pattern matching"""
        
        # Extract key information
        github_issues = []
        if github_findings.get("failed_checks"):
            github_issues.extend([check.get("name", "") for check in github_findings["failed_checks"]])
        if github_findings.get("health_issues"):
            github_issues.extend([issue.get("type", "") for issue in github_findings["health_issues"]])
        
        k8s_issues = []
        if k8s_findings.get("root_causes"):
            k8s_issues.extend(k8s_findings["root_causes"])
        
        github_text = " ".join(github_issues).lower()
        k8s_text = " ".join(k8s_issues).lower()
        
        # Pattern matching for common correlations
        if "health" in github_text and ("probe" in k8s_text or "readiness" in k8s_text or "liveness" in k8s_text):
            return {
                "correlation_found": True,
                "root_cause_chain": "GitHub health checks are failing because Kubernetes liveness/readiness probes are failing, indicating the application is not responding correctly to health checks",
                "primary_root_cause": "Application health probe configuration or application startup issues",
                "correlation_confidence": "high",
                "actionable_solution": "Fix application health endpoints or adjust probe configuration (initialDelaySeconds, timeoutSeconds)",
                "correlation_type": "health_probe"
            }
        
        elif "jenkins" in github_text and ("image" in k8s_text or "pull" in k8s_text):
            return {
                "correlation_found": True,
                "root_cause_chain": "GitHub CI/CD pipeline (Jenkins) is failing to build/push images, causing Kubernetes to fail pulling the container image",
                "primary_root_cause": "CI/CD pipeline build or image registry issues",
                "correlation_confidence": "high",
                "actionable_solution": "Fix Jenkins build pipeline and verify image registry credentials and connectivity",
                "correlation_type": "image_build"
            }
        
        elif "build" in github_text and ("crash" in k8s_text or "restart" in k8s_text):
            return {
                "correlation_found": True,
                "root_cause_chain": "GitHub build is failing or producing faulty code, causing the application to crash when deployed to Kubernetes",
                "primary_root_cause": "Application code issues or build configuration problems",
                "correlation_confidence": "medium",
                "actionable_solution": "Review application logs, fix code issues, and ensure proper build configuration",
                "correlation_type": "application_code"
            }
        
        elif ("secret" in k8s_text or "config" in k8s_text) and "deployment" in github_text:
            return {
                "correlation_found": True,
                "root_cause_chain": "GitHub deployment is failing because Kubernetes pods cannot start due to missing secrets or configuration",
                "primary_root_cause": "Missing or misconfigured secrets/configmaps in Kubernetes",
                "correlation_confidence": "high",
                "actionable_solution": "Create or update required secrets and configmaps in the target namespace",
                "correlation_type": "configuration"
            }
        
        else:
            return {
                "correlation_found": False,
                "root_cause_chain": "No clear correlation found between GitHub and Kubernetes issues",
                "primary_root_cause": "Issues appear to be independent or require deeper investigation",
                "correlation_confidence": "low",
                "actionable_solution": "Investigate GitHub and Kubernetes issues separately",
                "correlation_type": "other"
            }

