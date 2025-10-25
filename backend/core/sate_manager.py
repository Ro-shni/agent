"""
Manages the state of the DevOps workflow, including context creation
and summarization logic.
"""
from typing import Dict, Any

class StateManager:
    """Handles the creation and management of the workflow state."""

    @staticmethod
    def create_rag_context(github_response, kubernetes_response, jenkins_response, state) -> Dict[str, Any]:
        """Create context for RAG service from current findings"""
        context = {}
        
        # Extract namespace and environment from Kubernetes response
        if kubernetes_response and kubernetes_response.findings:
            k8s_findings = kubernetes_response.findings
            context["namespace"] = k8s_findings.get("namespace")
            context["environment"] = k8s_findings.get("environment")
            
            # Extract services from unhealthy pods
            unhealthy_pods = k8s_findings.get("unhealthy_pods", [])
            services = []
            for pod in unhealthy_pods:
                pod_name = pod.get("name", "")
                if pod_name:
                    # Extract service name from pod name (remove deployment hash)
                    import re
                    service_name = re.sub(r'-[a-z0-9]{8,10}-[a-z0-9]{5}$', '', pod_name)
                    service_name = re.sub(r'-[0-9]+$', '', service_name)
                    if service_name not in services:
                        services.append(service_name)
            context["services"] = services
            
            # Extract issue type and error patterns
            root_causes = k8s_findings.get("root_causes", [])
            context["issue_type"] = k8s_findings.get("issue_type", "unknown")
            context["error_patterns"] = root_causes
        
        # Extract GitHub context
        if github_response and github_response.findings:
            github_findings = github_response.findings
            failed_checks = github_findings.get("failed_checks", [])
            error_patterns = []
            for check in failed_checks:
                if check.get("details"):
                    error_patterns.append(check["details"])
            if error_patterns:
                context["error_patterns"] = context.get("error_patterns", []) + error_patterns
        
        # Extract Jenkins context
        if jenkins_response and jenkins_response.findings:
            jenkins_findings = jenkins_response.findings
            analysis = jenkins_findings.get("analysis", {})
            if analysis.get("error_details"):
                context["error_patterns"] = context.get("error_patterns", []) + analysis["error_details"]
        
        return context
    