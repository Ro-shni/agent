"""
Handles the routing logic for the LangGraph workflow, determining the
next agent to execute based on the current state.
"""
from ..models.workflow import DevOpsWorkflowState

class RoutingLogic:
    """Contains all the conditional routing logic for the orchestrator."""

    def intelligent_routing_logic(self, state: DevOpsWorkflowState) -> str:
        """Intelligent routing logic based on current state"""
        
        # Check if we have routing decisions
        routing_decisions = state.get("routing_decisions", [])
        if routing_decisions:
            latest_decision = routing_decisions[-1]
            return latest_decision.next_agent
        
        # Default initial routing based on task analysis
        task_analysis = state.get("task_analysis")
        if task_analysis:
            return task_analysis.task_type
        
        return "github"  # Default fallback
    
    def post_github_routing_fixed(self, state: DevOpsWorkflowState) -> str:
        """FIXED: Routing logic after GitHub agent execution"""
        
        github_response = state.get("github_response")
        if not github_response:
            return "summarizer"
        
        # Check if GitHub agent detected specific routing needs
        findings = github_response.findings
        
        # Check for direct routing signals from GitHub agent
        if findings.get("status") == "route_to_k8s":
            print(f"🔄 GitHub agent detected health check failures - routing to Kubernetes")
            return "kubernetes"
        
        if findings.get("status") == "route_to_jenkins":
            print(f"🔄 GitHub agent detected Jenkins build failures - routing to Jenkins")
            return "jenkins"
        
        # FIXED: Only route to Kubernetes if GitHub found ACTUAL CI/CD failures
        has_ci_cd_failures = False
        has_jenkins_failures = False
        
        # Check CI/CD status from the actual GitHub agent structure
        analysis = findings.get("analysis", {})
        detailed_analysis = analysis.get("detailed_analysis", {})
        ci_analysis = detailed_analysis.get("ci_cd", {})
        
        if ci_analysis.get("has_failures", False):
            has_ci_cd_failures = True
            print(f"🔄 GitHub found CI/CD failures - routing to Kubernetes for impact analysis")
        elif ci_analysis.get("status") == "Failing":
            has_ci_cd_failures = True
            print(f"🔄 GitHub found failing CI/CD checks - routing to Kubernetes for impact analysis")
        
        # Check for health check failures specifically in failing checks
        failing_checks = ci_analysis.get("failing_checks", [])
        for check in failing_checks:
            check_name = check.get("name", "").lower()
            if any(keyword in check_name for keyword in ["health", "deployment", "k8s", "kubernetes", "probe"]):
                has_ci_cd_failures = True
                print(f"🔄 GitHub found health/deployment check failure: {check_name} - routing to Kubernetes")
                break
            elif any(keyword in check_name for keyword in ["jenkins", "build", "ci/cd", "continuous-integration"]):
                has_jenkins_failures = True
                print(f"🔄 GitHub found Jenkins/CI failure: {check_name} - routing to Jenkins")
                break
        
        # Check issue comments for health check failures (bot notifications)
        issue_comments_analysis = detailed_analysis.get("issue_comments", {})
        bot_comments = issue_comments_analysis.get("bot_comments", [])
        
        for comment in bot_comments:
            comment_body = comment.get("body", "").lower()
            if any(keyword in comment_body for keyword in ["health check", "healthcheck", "probe", "deployment", "k8s", "kubernetes", "did not complete successfully"]):
                has_ci_cd_failures = True
                print(f"🔄 GitHub found health check failure in bot comments - routing to Kubernetes")
                break
            elif any(keyword in comment_body for keyword in ["jenkins", "build failed", "ci workflow", "waitforjenkinsjobcompletionactivity"]):
                has_jenkins_failures = True
                print(f"🔄 GitHub found Jenkins failure in bot comments - routing to Jenkins")
                break
        
        # Check if there are issues that suggest deployment problems
        pr_health = findings.get("pr_health", "")
        if pr_health in ["Has Issues", "Needs Attention", "Failing"]:
            issues = findings.get("issues", [])
            for issue in issues:
                if any(keyword in issue.lower() for keyword in 
                       ["ci/cd", "build", "deployment", "health", "failing", "k8s", "kubernetes", "probe"]):
                    has_ci_cd_failures = True
                    print(f"🔄 GitHub found deployment-related issues - routing to Kubernetes for impact analysis")
                    break
                elif any(keyword in issue.lower() for keyword in ["jenkins", "build", "ci"]):
                    has_jenkins_failures = True
                    print(f"🔄 GitHub found Jenkins-related issues - routing to Jenkins for analysis")
                    break
        
        # Check for specific health check keywords in the user prompt
        user_prompt = state.get("user_prompt", "").lower()
        if any(keyword in user_prompt for keyword in ["health", "degraded", "unhealthy", "probe", "crash", "restart"]):
            has_ci_cd_failures = True
            print(f"🔄 User mentioned health/K8s issues - routing to Kubernetes for analysis")
        elif any(keyword in user_prompt for keyword in ["jenkins", "build", "ci/cd", "pipeline"]):
            has_jenkins_failures = True
            print(f"🔄 User mentioned Jenkins/CI issues - routing to Jenkins for analysis")
        
        # Check the raw analysis text for health check failures
        analysis_text = findings.get("analysis_text", "").lower()
        if any(keyword in analysis_text for keyword in ["health check did not complete successfully", "health check failure", "deployment failed", "probe failure"]):
            has_ci_cd_failures = True
            print(f"🔄 GitHub analysis text contains health check failures - routing to Kubernetes")
        elif any(keyword in analysis_text for keyword in ["jenkins build failed", "ci workflow did not complete", "build failed"]):
            has_jenkins_failures = True
            print(f"🔄 GitHub analysis text contains Jenkins failures - routing to Jenkins")
        
        # Check execution status
        kubernetes_executed = state.get("kubernetes_response") is not None
        jenkins_executed = state.get("jenkins_response") is not None
        
        # Priority: Jenkins first (more specific), then Kubernetes (broader)
        if has_jenkins_failures and not jenkins_executed:
            return "jenkins"
        elif has_ci_cd_failures and not kubernetes_executed:
            return "kubernetes"
        
        return "summarizer"
    
    def post_kubernetes_routing_fixed(self, state: DevOpsWorkflowState) -> str:
        """FIXED: Routing logic after Kubernetes agent execution"""
        
        # After Kubernetes, usually go to summarizer unless we need GitHub context
        github_executed = state.get("github_response") is not None
        
        # FIXED: Only go to GitHub if user explicitly mentioned PR/GitHub AND we found K8s issues
        kubernetes_response = state.get("kubernetes_response")
        if kubernetes_response and kubernetes_response.findings.get("root_causes") and not github_executed:
            # Only go to GitHub if the user prompt EXPLICITLY suggests there might be a PR/issue
            user_prompt = state.get("user_prompt", "").lower()
            if ("pr" in user_prompt or "pull request" in user_prompt or "github.com" in user_prompt):
                print(f"🔄 User mentioned PR/GitHub and K8s found issues - routing to GitHub for context")
                return "github"
        
        return "summarizer"
    
    def post_jenkins_routing_fixed(self, state: DevOpsWorkflowState) -> str:
        """FIXED: Routing logic after Jenkins agent execution"""
        
        # After Jenkins, check if we need Kubernetes analysis for impact
        jenkins_response = state.get("jenkins_response")
        if jenkins_response and jenkins_response.findings.get("analysis"):
            analysis = jenkins_response.findings["analysis"]
            # If Jenkins found build/test failure, route to Kubernetes for impact analysis
            if analysis.get("failure_type") in ["build_failure", "test_failure"]:
                print(f"🔄 Jenkins found build/test failure - routing to Kubernetes for impact analysis")
                return "kubernetes"
        
        return "summarizer"
    