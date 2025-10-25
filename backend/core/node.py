"""
Contains the implementation of all nodes used in the LangGraph workflow.
Each method in the OrchestratorNodes class corresponds to a node in the graph.
"""
from ..models.workflow import DevOpsWorkflowState, RoutingDecision, AgentResponse
from ..utils.detectors import DevOpsNamespaceDetector
from ..utils.cluster_manager import SmartClusterManager
from ..prompts import ORCHESTRATOR_SYSTEM_PROMPT,ORCHESTRATOR_USER_PROMPT_TEMPLATE, get_orchestrator_prompt, get_intelligent_summarizer_prompt
from langchain_core.prompts import ChatPromptTemplate
# from ..core.orchestrator import UnifiedDevOpsOrchestrator
from typing import TYPE_CHECKING, Dict, Any
from ..utils.detectors import Detector 
import json
import re
from ..prompts.summarizer import FINAL_RESPONSE_SYSTEM_PROMPT, FINAL_RESPONSE_USER_PROMPT_TEMPLATE
from langchain_core.prompts import ChatPromptTemplate

if TYPE_CHECKING:
    from ..core.orchestrator import UnifiedDevOpsOrchestrator

class Nodes:
    """A class that holds the logic for each node in the workflow."""
    def __init__(self,orchestrator:"UnifiedDevOpsOrchestrator"):
        self.orchestrator = orchestrator
     
    async def orchestrator_node(self, state: DevOpsWorkflowState) -> DevOpsWorkflowState:
        """INTELLIGENT orchestrator node with dynamic routing"""
        
        print("🧠 Orchestrator: Analyzing task and making intelligent routing decision...")
        
        # Check if this is initial routing or re-routing
        routing_decisions = state.get("routing_decisions", [])
        is_initial = len(routing_decisions) == 0
        
        if is_initial:
            # URL-based routing first, then LLM analysis for context
            # detected_type = Detector.detect_url_type(state["user_prompt"])
            
            # if detected_type != "general":
            #     # URL-based routing
            #     routing_decision = RoutingDecision(
            #         next_agent=detected_type,
            #         reasoning=f"URL pattern detected: {detected_type}",
            #         confidence="high",
            #         context_needed=[]
            #     )
            # else:
                # Use centralized orchestrator prompt
            orchestrator_prompt = ChatPromptTemplate.from_template(
                ORCHESTRATOR_SYSTEM_PROMPT + "\n\n" + ORCHESTRATOR_USER_PROMPT_TEMPLATE
            )                
            task_type = "unavailable_agent"  # default
            reasoning = "Default routing"
            confidence = "low"

            try:
                orchestrator_chain = orchestrator_prompt | self.orchestrator.services.llm
                
                response = await orchestrator_chain.ainvoke({
                    "user_prompt": state["user_prompt"]
                })
                
                # Parse the response manually since structured output is having issues
                content = response.content.strip()
                json_content = content
                if "```json" in content:
                    json_content = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_content:
                        json_content = json_content.group(1)
                routing_data = json.loads(json_content)
                task_type = routing_data.get("agent", "unavailable_agent")
                reasoning = routing_data.get("reasoning", "No reasoning provided")
                confidence_raw = routing_data.get("confidence", "low")
                valid_agents = ["github", "kubernetes", "jenkins", "unavailable_agent"]
                if task_type not in valid_agents:
                    task_type = "unavailable_agent"
                    reasoning = f"Invalid agent '{task_type}' - routing to unavailable_agent"
                    confidence = "low"
                
                if confidence_raw in ["high", "medium", "low"]:
                    confidence = confidence_raw
                else:
                    confidence = "low"  # fallback

                print(f"🔍 Orchestrator response: {content}")
                # Simple parsing logic
                # if "kubernetes" in content.lower() or "k8s" in content.lower() or "pod" in content.lower() or "namespace" in content.lower():
                #     task_type = "kubernetes"
                #     reasoning = "Detected Kubernetes-related query"
                # elif "jenkins" in content.lower() or "build" in content.lower() or "ci/cd" in content.lower():
                #     task_type = "jenkins"
                #     reasoning = "Detected Jenkins/build-related query"
                # elif "github" in content.lower() or "pr" in content.lower() or "pull request" in content.lower():
                #     task_type = "github"
                #     reasoning = "Detected GitHub/PR-related query"
                # else:
                #     task_type = "summarizer"  # Default to summarizer for non-DevOps queries
                #     reasoning = "No specific DevOps agent detected - routing to summarizer for general analysis"
                
                
            except Exception as e:
                print(f"❌ LLM routing failed: {str(e)}")
                # Smart fallback routing based on content
                user_prompt_lower = state["user_prompt"].lower()
                if any(word in user_prompt_lower for word in ["pod", "namespace", "k8s", "kubernetes", "crash", "health", "deploy"]):
                    task_type = "kubernetes"
                    reasoning = "Content-based routing to Kubernetes"
                elif any(word in user_prompt_lower for word in ["jenkins", "build", "ci/cd", "console"]):
                    task_type = "jenkins"
                    reasoning = "Content-based routing to Jenkins"
                elif any(word in user_prompt_lower for word in ["github", "pr", "pull request"]):
                    task_type = "github"
                    reasoning = "Content-based routing to GitHub"
                else:
                    task_type = "unavailable_agent"  # Default to unavailable_agent for non-DevOps queries
                    reasoning = "No specific DevOps patterns detected - routing to unavailable_agent"
                confidence= "low"
                # routing_decision = RoutingDecision(
                #     next_agent=task_type,
                #     reasoning=reasoning,
                #     confidence="medium",
                #     context_needed=[]
                # )
        
            routing_decision = RoutingDecision(
                next_agent=task_type,
                reasoning=reasoning,
                confidence=confidence,
                context_needed=[]
            )

            print(f"🧠 Initial Orchestrator Decision:")
            print(f"   Route: {routing_decision.next_agent.upper()}")
            print(f"   Confidence: {routing_decision.confidence.upper()}")
            print(f"   Reasoning: {routing_decision.reasoning}")
            
            # Initialize state
            agent_memory = {
                "user_request": state["user_prompt"],
                "initial_routing": routing_decision.next_agent,
                "context_summary": "Starting intelligent analysis"
            }
            
            execution_history = [{
                "step": 1,
                "action": "initial_intelligent_routing",
                "agent": "orchestrator",
                "decision": routing_decision.next_agent,
                "reasoning": routing_decision.reasoning
            }]
            
            agent_status = {
                "github": "not_executed",
                "kubernetes": "not_executed"
            }
            
            return {
                **state,
                "task_analysis": analysis if 'analysis' in locals() else None,
                "routing_decisions": [routing_decision],
                "agent_memory": agent_memory,
                "execution_history": execution_history,
                "agent_status": agent_status
            }
        
        else:
            # Re-routing based on previous findings
            print("🧠 Orchestrator: Making intelligent re-routing decision based on findings...")
            
            github_response = state.get("github_response")
            kubernetes_response = state.get("kubernetes_response")
            
            # Intelligent re-routing logic
            next_agent = "summarizer"  # Default
            reasoning = "Analysis complete - ready for intelligent summarization"
            
            # FIXED: Only route to K8s if GitHub found ACTUAL health/deployment issues
            if github_response and not kubernetes_response:
                github_findings = github_response.findings
                
                # Check detailed analysis for failures
                analysis = github_findings.get("analysis", {})
                detailed_analysis = analysis.get("detailed_analysis", {})
                ci_analysis = detailed_analysis.get("ci_cd", {})
                has_real_issues = False
                
                # Check for CI/CD failures
                if ci_analysis.get("has_failures", False) or ci_analysis.get("status") == "Failing":
                    has_real_issues = True
                    reasoning = "GitHub found CI/CD failures requiring Kubernetes investigation"
                
                # Check for health check failures specifically in failing checks
                failing_checks = ci_analysis.get("failing_checks", [])
                for check in failing_checks:
                    check_name = check.get("name", "").lower()
                    if any(keyword in check_name for keyword in ["health", "deployment", "k8s", "kubernetes", "probe"]):
                        has_real_issues = True
                        reasoning = f"GitHub found health/deployment check failure: {check_name} - routing to Kubernetes"
                        break
                
                # Check issue comments for health check failures (bot notifications)
                issue_comments_analysis = detailed_analysis.get("issue_comments", {})
                bot_comments = issue_comments_analysis.get("bot_comments", [])
                
                for comment in bot_comments:
                    comment_body = comment.get("body", "").lower()
                    if any(keyword in comment_body for keyword in ["health check", "healthcheck", "probe", "deployment", "k8s", "kubernetes"]):
                        has_real_issues = True
                        reasoning = "GitHub found health check failure in bot comments - routing to Kubernetes"
                        break
                
                # Check PR health status
                pr_health = github_findings.get("pr_health", "")
                if pr_health in ["Has Issues", "Needs Attention", "Failing"]:
                    has_real_issues = True
                    reasoning = "GitHub found PR health issues requiring Kubernetes investigation"
                
                if has_real_issues:
                    next_agent = "kubernetes"
            
            # If K8s found issues but GitHub not executed and user mentioned PR
            elif kubernetes_response and not github_response:
                user_prompt = state.get("user_prompt", "").lower()
                if ("pr" in user_prompt or "github" in user_prompt) and kubernetes_response.findings.get("root_causes"):
                    next_agent = "github"
                    reasoning = "Kubernetes found issues and user mentioned PR - checking GitHub for related context"
            
            routing_decision = RoutingDecision(
                next_agent=next_agent,
                reasoning=reasoning,
                confidence="high",
                context_needed=[]
            )
            
            print(f"🧠 Re-routing Decision:")
            print(f"   Next Agent: {routing_decision.next_agent.upper()}")
            print(f"   Reasoning: {routing_decision.reasoning}")
            
            # Update routing decisions
            updated_decisions = routing_decisions + [routing_decision]
            
            execution_history = state.get("execution_history", [])
            execution_history.append({
                "step": len(execution_history) + 1,
                "action": "intelligent_re_routing",
                "agent": "orchestrator",
                "decision": routing_decision.next_agent,
                "reasoning": routing_decision.reasoning
            })
            
            return {
                **state,
                "routing_decisions": updated_decisions,
                "execution_history": execution_history
            }

    async def github_agent_node(self, state: DevOpsWorkflowState) -> DevOpsWorkflowState:
        """GitHub agent for PR analysis and CI/CD checks with health check routing"""
        
        print("🔧 GitHub Agent: Starting intelligent GitHub analysis...")
        
        try:
            # Initialize GitHub agent
            github_agent = self.orchestrator.github_agent
            await github_agent.initialize()
            
            # Analyze GitHub PR
            github_analysis = await github_agent.analyze(state["user_prompt"])
            
            # Check if GitHub agent detected health check failures that should route to K8s
            if github_analysis.get("status") == "route_to_k8s":
                print("🔧 GitHub Agent: Health check failures detected, routing to Kubernetes agent...")
                
                # Extract health check info for K8s routing
                health_check_info = github_analysis.get("health_check_info", {})
                environment = health_check_info.get("environment", "stg")
                applications = health_check_info.get("applications", [])
                
                # Create a modified user prompt for K8s agent with health check context
                k8s_prompt = f"Health check failures detected in GitHub PR for environment: {environment}, applications: {', '.join(applications)}. Please analyze the Kubernetes cluster for these applications."
                
                # Update the state to route to K8s agent
                updated_memory = state.get("agent_memory", {}).copy()
                updated_memory["github_health_check_info"] = health_check_info
                updated_memory["routing_reason"] = "Health check failures detected in GitHub PR"
                
                execution_history = state.get("execution_history", []).copy()
                execution_history.append({
                    "step": len(execution_history) + 1,
                    "action": "github_health_check_detection",
                    "agent": "github",
                    "status": "routing_to_k8s",
                    "health_check_info": health_check_info
                })
                
                updated_status = state.get("agent_status", {}).copy()
                updated_status["github"] = "routing_to_k8s"
                
                # Update the user prompt for K8s agent
                state["user_prompt"] = k8s_prompt
                
                print(f"🔧 Routing to K8s with: {k8s_prompt}")
                
                return {
                    **state,
                    "github_response": AgentResponse(
                        agent_name="GitHub Agent",
                        status="routing_to_k8s",
                        findings={"health_check_info": health_check_info},
                        next_actions=["Routing to Kubernetes agent for health check analysis"]
                    ),
                    "agent_memory": updated_memory,
                    "execution_history": execution_history,
                    "agent_status": updated_status
                }
            
            # Check if GitHub agent detected Jenkins build failures that should route to Jenkins
            if github_analysis.get("status") == "route_to_jenkins":
                print("🔧 GitHub Agent: Jenkins build failures detected, routing to Jenkins agent...")
                
                # Extract Jenkins failure info for Jenkins routing
                jenkins_failure_info = github_analysis.get("jenkins_failure_info", {})
                jenkins_urls = jenkins_failure_info.get("jenkins_urls", [])
                
                # Create a modified user prompt for Jenkins agent with Jenkins URL context
                jenkins_prompt = f"Jenkins build failures detected in GitHub PR. Please analyze the following Jenkins build URLs: {', '.join(jenkins_urls)}"
                
                # Update the state to route to Jenkins agent
                updated_memory = state.get("agent_memory", {}).copy()
                updated_memory["github_jenkins_failure_info"] = jenkins_failure_info
                updated_memory["routing_reason"] = "Jenkins build failures detected in GitHub PR"
                
                execution_history = state.get("execution_history", []).copy()
                execution_history.append({
                    "step": len(execution_history) + 1,
                    "action": "github_jenkins_failure_detection",
                    "agent": "github",
                    "status": "routing_to_jenkins",
                    "jenkins_failure_info": jenkins_failure_info
                })
                
                updated_status = state.get("agent_status", {}).copy()
                updated_status["github"] = "routing_to_jenkins"
                
                # Update the user prompt for Jenkins agent
                state["user_prompt"] = jenkins_prompt
                
                print(f"🔧 Routing to Jenkins with: {jenkins_prompt}")
                
                return {
                    **state,
                    "github_response": AgentResponse(
                        agent_name="GitHub Agent",
                        status="routing_to_jenkins",
                        findings={"jenkins_failure_info": jenkins_failure_info},
                        next_actions=["Routing to Jenkins agent for build failure analysis"]
                    ),
                    "agent_memory": updated_memory,
                    "execution_history": execution_history,
                    "agent_status": updated_status
                }
            
            # Display the detailed analysis
            if github_analysis.get("analysis_text"):
                print("\n" + "="*50)
                print("📊 GitHub PR Analysis Results:")
                print("="*50)
                print(github_analysis["analysis_text"])
                print("="*50)
            
            github_response = AgentResponse(
                agent_name="GitHub Agent",
                status=github_analysis.get("status", "success"),
                findings=github_analysis,
                errors=github_analysis.get("errors", []),
                next_actions=github_analysis.get("recommendations", [])
            )
            
            # Update state
            updated_memory = state.get("agent_memory", {}).copy()
            updated_memory["github_findings"] = github_analysis
            
            execution_history = state.get("execution_history", []).copy()
            execution_history.append({
                "step": len(execution_history) + 1,
                "action": "github_pr_analysis",
                "agent": "github",
                "status": github_response.status,
                "pr_info": github_analysis.get("pr_info", {})
            })
            
            updated_status = state.get("agent_status", {}).copy()
            updated_status["github"] = "completed" if github_response.status == "success" else "failed"
            
            print("✅ GitHub Agent: Analysis completed")
            if github_analysis.get("analysis"):
                print(f"📊 GitHub Findings:")
                print(f"   • PR Health: {github_analysis['analysis'].get('pr_health', 'Unknown')}")
                print(f"   • CI Status: {github_analysis['analysis'].get('ci_status', 'Unknown')}")
                print(f"   • Issues: {len(github_analysis['analysis'].get('issues', []))}")
                print(f"   • Recommendations: {len(github_analysis['analysis'].get('recommendations', []))}")
            
            return {
                **state,
                "github_response": github_response,
                "agent_memory": updated_memory,
                "execution_history": execution_history,
                "agent_status": updated_status
            }
            
        except Exception as e:
            print(f"❌ GitHub Agent error: {str(e)}")
            
            github_response = AgentResponse(
                agent_name="GitHub Agent",
                status="failed",
                errors=[{"source": "github_agent", "error": str(e)}],
                next_actions=["Check GitHub connectivity", "Verify PR URL"]
            )
            
            updated_status = state.get("agent_status", {}).copy()
            updated_status["github"] = "failed"
            
            return {
                **state,
                "github_response": github_response,
                "agent_status": updated_status
            }

    async def kubernetes_agent_nodeold(self, state: DevOpsWorkflowState) -> DevOpsWorkflowState:
        """Enhanced Kubernetes agent with FIXED cluster switching"""
        
        print("☸️ Kubernetes Agent: Starting intelligent systematic debugging...")
        
        if not self.orchestrator.services.kubernetes_tools or not self.orchestrator.services.kubernetes_debugger:
            print("❌ Kubernetes Agent: No tools available")
            updated_status = state.get("agent_status", {}).copy()
            updated_status["kubernetes"] = "failed"
            
            return {
                **state,
                "kubernetes_response": AgentResponse(
                    agent_name="Kubernetes Agent",
                    status="failed",
                    errors=[{"source": "kubernetes_agent", "error": "Kubernetes tools not available"}],
                    next_actions=["Initialize Kubernetes tools"]
                ),
                "agent_status": updated_status
            }
        
        try:
            # FIXED: Extract namespace info from user prompt using MySQL-integrated detector
            from ..utils.detectors import namespace_detector
            namespace_info = await namespace_detector.extract_namespace_info_from_user_input(state["user_prompt"])
            
            print(f"☸️ Intelligent Detection Results:")
            print(f"   • Issue Type: {namespace_info.get('issue_type', 'unknown').upper()}")
            print(f"   • Severity: {namespace_info.get('severity', 'medium').upper()}")
            print(f"   • Environment: {namespace_info.get('environment', 'unknown')}")
            print(f"   • Business Unit: {namespace_info.get('business_unit', 'unknown')}")
            print(f"   • Applications: {namespace_info.get('applications', [])}")
            print(f"   • Namespaces: {namespace_info.get('namespaces', [])}")
            
            # FIXED: Handle cluster context switching
            cluster_switched = await SmartClusterManager.handle_cluster_switching_fixed(namespace_info)
            
            if not namespace_info.get("namespaces"):
                kubernetes_response = AgentResponse(
                    agent_name="Kubernetes Agent",
                    status="failed",
                    errors=[{"source": "kubernetes_agent", "error": "Could not determine target namespace from request"}],
                    next_actions=["Provide application name and environment (e.g., 'stg-app-name')", "Specify the Kubernetes namespace to investigate"]
                )
            else:
                # Run perfected Kubernetes debugging
                target_namespace = namespace_info["namespaces"][0]
                environment = namespace_info.get("environment", "stg")
                business_unit = namespace_info.get("business_unit", "central")
                
                k8s_findings = await self.orchestrator.services.kubernetes_debugger.debug_application_health(
                    target_namespace, 
                    environment, 
                    business_unit
                )
                
                kubernetes_response = AgentResponse(
                    agent_name="Kubernetes Agent",
                    status="success",
                    findings=k8s_findings,
                    errors=k8s_findings.get("errors", []),
                    next_actions=k8s_findings.get("immediate_actions", [])
                )
            
            # Update state
            updated_memory = state.get("agent_memory", {}).copy()
            updated_memory["kubernetes_findings"] = kubernetes_response.findings
            
            execution_history = state.get("execution_history", []).copy()
            execution_history.append({
                "step": len(execution_history) + 1,
                "action": "intelligent_kubernetes_debugging",
                "agent": "kubernetes",
                "status": kubernetes_response.status,
                "namespace": target_namespace if namespace_info.get("namespaces") else "unknown",
                "cluster_switched": cluster_switched
            })
            
            updated_status = state.get("agent_status", {}).copy()
            updated_status["kubernetes"] = "completed" if kubernetes_response.status == "success" else "failed"
            
            print("✅ Kubernetes Agent: Intelligent analysis completed")
            if kubernetes_response.findings:
                events_count = len(kubernetes_response.findings.get("events", []))
                pod_issues_count = len(kubernetes_response.findings.get("unhealthy_pods", []))
                root_causes_count = len(kubernetes_response.findings.get("root_causes", []))
                print(f"📊 Kubernetes Findings:")
                print(f"   • Events: {events_count}")
                print(f"   • Unhealthy Pods: {pod_issues_count}")
                print(f"   • Root Causes: {root_causes_count}")
            
            return {
                **state,
                "kubernetes_response": kubernetes_response,
                "agent_memory": updated_memory,
                "execution_history": execution_history,
                "agent_status": updated_status
            }
            
        except Exception as e:
            print(f"❌ Kubernetes Agent error: {str(e)}")
            
            updated_status = state.get("agent_status", {}).copy()
            updated_status["kubernetes"] = "failed"
            
            return {
                **state,
                "kubernetes_response": AgentResponse(
                    agent_name="Kubernetes Agent",
                    status="failed",
                    errors=[{"source": "kubernetes_agent", "error": str(e)}],
                    next_actions=["Check Kubernetes connection", "Verify cluster access"]
                ),
                "agent_status": updated_status
            }
    
    async def kubernetes_agent_node(self, state: DevOpsWorkflowState) -> DevOpsWorkflowState:
        """Enhanced Kubernetes agent with FIXED cluster switching and GitHub health check routing"""
        
        print("☸️ Kubernetes Agent: Starting intelligent systematic debugging...")
        
        if not self.orchestrator.services.kubernetes_tools or not self.orchestrator.services.kubernetes_debugger:
            print("❌ Kubernetes Agent: No tools available")
            updated_status = state.get("agent_status", {}).copy()
            updated_status["kubernetes"] = "failed"
            
            return {
                **state,
                "kubernetes_response": AgentResponse(
                    agent_name="Kubernetes Agent",
                    status="failed",
                    errors=[{"source": "kubernetes_agent", "error": "Kubernetes tools not available"}],
                    next_actions=["Initialize Kubernetes tools"]
                ),
                "agent_status": updated_status
            }
        
        try:
            # Check if this is a health check routing from GitHub
            cluster_switched = False
            github_health_check_info = state.get("agent_memory", {}).get("github_health_check_info")
            
            if github_health_check_info:
                print("☸️ Kubernetes Agent: Processing health check failures from GitHub PR...")
                
                # Use health check info from GitHub
                environment = github_health_check_info.get("environment", "stg")
                applications = github_health_check_info.get("applications", [])
                failures = github_health_check_info.get("failures", [])
                
                print(f"☸️ Health Check Context:")
                print(f"   • Environment: {environment}")
                print(f"   • Applications: {applications}")
                print(f"   • Failures: {len(failures)} detected")
                
                # Create namespace info from health check context
                namespace_info = {
                    "environment": environment,
                    "applications": applications,
                    "namespaces": [f"{environment}-{app}" for app in applications],
                    "issue_type": "health_check",
                    "severity": "high",
                    "business_unit": None  # Will be detected by MySQL lookup
                }
                
                # Get business unit for the first application
                if applications:
                    from ..utils.detectors import namespace_detector
                    app_bu = await namespace_detector._get_business_unit_for_app(applications[0])
                    if app_bu:
                        namespace_info["business_unit"] = app_bu
                        print(f"   • Business Unit: {app_bu}")
                
                # Get cluster context
                if namespace_info["business_unit"]:
                    cluster_context = await namespace_detector._find_matching_context(
                        namespace_info["business_unit"], 
                        namespace_info["environment"]
                    )
                    namespace_info["cluster_context_needed"] = cluster_context
                    cluster_switched = await SmartClusterManager.handle_cluster_switching_fixed(namespace_info)
                
            else:
                # FIXED: Extract namespace info from user prompt using MySQL-integrated detector
                from ..utils.detectors import namespace_detector
                namespace_info = await namespace_detector.extract_namespace_info_from_user_input(state["user_prompt"])
            
            print(f"☸️ Intelligent Detection Results:")
            print(f"   • Issue Type: {namespace_info.get('issue_type', 'unknown').upper()}")
            print(f"   • Severity: {namespace_info.get('severity', 'medium').upper()}")
            print(f"   • Environment: {namespace_info.get('environment', 'unknown')}")
            print(f"   • Business Unit: {namespace_info.get('business_unit', 'unknown')}")
            print(f"   • Applications: {namespace_info.get('applications', [])}")
            print(f"   • Namespaces: {namespace_info.get('namespaces', [])}")
            
            # FIXED: Handle cluster context switching
            cluster_switched = await SmartClusterManager.handle_cluster_switching_fixed(namespace_info)
            
            if not namespace_info.get("namespaces"):
                kubernetes_response = AgentResponse(
                    agent_name="Kubernetes Agent",
                    status="failed",
                    errors=[{"source": "kubernetes_agent", "error": "Could not determine target namespace from request"}],
                    next_actions=["Provide application name and environment (e.g., 'stg-app-name')", "Specify the Kubernetes namespace to investigate"]
                )
            else:
                # Run perfected Kubernetes debugging for each namespace
                all_findings = []
                all_errors = []
                all_actions = []
                
                for namespace in namespace_info["namespaces"]:
                    environment = namespace_info.get("environment", "stg")
                    business_unit = namespace_info.get("business_unit", "central")
                    
                    print(f"☸️ Debugging namespace: {namespace}")
                    
                    k8s_findings = await self.orchestrator.services.kubernetes_debugger.debug_application_health(
                        namespace, 
                        environment, 
                        business_unit
                    )
                    
                    print(f"☸️ Namespace {namespace} findings: {k8s_findings}")
                    
                    if k8s_findings:
                        all_findings.append(k8s_findings)
                        all_errors.extend(k8s_findings.get("errors", []))
                        all_actions.extend(k8s_findings.get("immediate_actions", []))
                
                # Combine findings from all namespaces
                combined_findings = self._combine_k8s_findings(all_findings, namespace_info)
                
                kubernetes_response = AgentResponse(
                    agent_name="Kubernetes Agent",
                    status="success",
                    findings=combined_findings,
                    errors=all_errors,
                    next_actions=all_actions
                )
            
            # Update state
            updated_memory = state.get("agent_memory", {}).copy()
            updated_memory["kubernetes_findings"] = kubernetes_response.findings
            updated_memory["namespace_info"] = namespace_info
            updated_memory["cluster_switched"] = cluster_switched
            
            execution_history = state.get("execution_history", []).copy()
            execution_history.append({
                "step": len(execution_history) + 1,
                "action": "intelligent_kubernetes_debugging",
                "agent": "kubernetes", 
                "status": kubernetes_response.status,
                "namespaces": namespace_info.get("namespaces", []),
                "cluster_switched": cluster_switched
            })
            
            updated_status = state.get("agent_status", {}).copy()
            updated_status["kubernetes"] = "completed" if kubernetes_response.status == "success" else "failed"
            
            print("✅ Kubernetes Agent: Intelligent analysis completed")
            if kubernetes_response.findings:
                events_count = len(kubernetes_response.findings.get("events", []))
                pod_issues_count = len(kubernetes_response.findings.get("unhealthy_pods", []))
                root_causes_count = len(kubernetes_response.findings.get("root_causes", []))
                print(f"📊 Kubernetes Findings:")
                print(f"   • Events: {events_count}")
                print(f"   • Unhealthy Pods: {pod_issues_count}")
                print(f"   • Root Causes: {root_causes_count}")
            
            return {
                **state,
                "kubernetes_response": kubernetes_response,
                "agent_memory": updated_memory,
                "execution_history": execution_history,
                "agent_status": updated_status
            }
            
        except Exception as e:
            print(f"❌ Kubernetes Agent error: {str(e)}")
            
            updated_status = state.get("agent_status", {}).copy()
            updated_status["kubernetes"] = "failed"
            
            return {
                **state,
                "kubernetes_response": AgentResponse(
                    agent_name="Kubernetes Agent",
                    status="failed",
                    errors=[{"source": "kubernetes_agent", "error": str(e)}],
                    next_actions=["Check Kubernetes connection", "Verify cluster access"]
                ),
                "agent_status": updated_status
            }

    async def jenkins_agent_node(self, state: DevOpsWorkflowState) -> DevOpsWorkflowState:
        """Jenkins agent for build failure analysis"""
        
        print("🏗️ Jenkins Agent: Starting Jenkins build analysis...")
        
        try:
            # Import Jenkins agent from gptjenk.py
            # from jenkins_agent import JenkinsAgent
            
            # Initialize Jenkins agent
            # jenkins_agent = JenkinsAgent(self.orchestrator.services.llm, self.orchestrator.services.tool_logger)
            jenkins_agent = self.orchestrator.jenkins_agent
            await jenkins_agent.initialize()
            
            # Analyze Jenkins build failure
            jenkins_analysis = await jenkins_agent.analyze(state["user_prompt"])
            
            # Display the detailed analysis
            if jenkins_analysis.get("analysis_text"):
                print("\n" + "="*50)
                print("📊 Jenkins Build Analysis Results:")
                print("="*50)
                print(jenkins_analysis["analysis_text"])
                print("="*50)
            
            jenkins_response = AgentResponse(
                agent_name="Jenkins Agent",
                status=jenkins_analysis.get("status", "success"),
                findings=jenkins_analysis,
                errors=jenkins_analysis.get("errors", []),
                next_actions=jenkins_analysis.get("recommendations", [])
            )
            
            # Update state
            updated_memory = state.get("agent_memory", {}).copy()
            updated_memory["jenkins_findings"] = jenkins_analysis
            
            execution_history = state.get("execution_history", []).copy()
            execution_history.append({
                "step": len(execution_history) + 1,
                "action": "jenkins_build_analysis",
                "agent": "jenkins",
                "status": jenkins_response.status,
                "build_info": jenkins_analysis.get("build_info", {})
            })
            
            updated_status = state.get("agent_status", {}).copy()
            updated_status["jenkins"] = "completed" if jenkins_response.status == "success" else "failed"
            
            print("✅ Jenkins Agent: Analysis completed")
            if jenkins_analysis.get("analysis"):
                print(f"📊 Jenkins Findings:")
                print(f"   • Root Cause: {jenkins_analysis['analysis'].get('root_cause', 'Unknown')}")
                print(f"   • Failure Type: {jenkins_analysis['analysis'].get('failure_type', 'Unknown')}")
                print(f"   • Severity: {jenkins_analysis['analysis'].get('severity', 'Unknown')}")
                print(f"   • Confidence: {jenkins_analysis['analysis'].get('confidence', 'Unknown')}")
            
            return {
                **state,
                "jenkins_response": jenkins_response,
                "agent_memory": updated_memory,
                "execution_history": execution_history,
                "agent_status": updated_status
            }
            
        except Exception as e:
            print(f"❌ Jenkins Agent error: {str(e)}")
            
            jenkins_response = AgentResponse(
                agent_name="Jenkins Agent",
                status="failed",
                errors=[{"source": "jenkins_agent", "error": str(e)}],
                next_actions=["Check Jenkins connectivity", "Verify build URL"]
            )
            
            updated_status = state.get("agent_status", {}).copy()
            updated_status["jenkins"] = "failed"
            
            return {
                **state,
                "jenkins_response": jenkins_response,
                "agent_status": updated_status
            }

    async def intelligent_summarizer_node(self, state: DevOpsWorkflowState) -> DevOpsWorkflowState:
        """Enhanced intelligent summarizer with adaptive analysis"""
        
        print("📊 Intelligent Summarizer: Creating adaptive analysis...")
        
        github_response = state.get("github_response")
        kubernetes_response = state.get("kubernetes_response") 
        jenkins_response = state.get("jenkins_response")
        agent_count = sum([
        1 if github_response and github_response.findings else 0,
        1 if kubernetes_response and kubernetes_response.findings else 0,
        1 if jenkins_response and jenkins_response.findings else 0
        ])

        # NEW: Run correlation analysis if we have multiple agent findings
        # correlation_analysis = None
        # if (github_response and kubernetes_response and 
        #     github_response.findings and kubernetes_response.findings and
        #     self.orchestrator.correlation_engine):  # CRITICAL: Check if correlation_engine exists
        #     print("🧠 Running intelligent correlation analysis...")
        #     try:
        #         correlation_analysis = await self.orchestrator.correlation_engine.correlate_findings(
        #             github_response.findings,
        #             kubernetes_response.findings,
        #             state["user_prompt"]
        #         )
        #     except Exception as e:
        #         print(f"⚠️ Correlation analysis failed: {str(e)}")
        #         correlation_analysis = None
        correlation_analysis = None
        if agent_count >= 2 and self.orchestrator.correlation_engine:
            agents_present = []
            if github_response and github_response.findings:
                agents_present.append("GitHub")
            if kubernetes_response and kubernetes_response.findings:
                agents_present.append("Kubernetes")
            if jenkins_response and jenkins_response.findings:
                agents_present.append("Jenkins")
            
            print(f"🧠 GGG Running intelligent correlation analysis for: {' + '.join(agents_present)}...")
            
            try:
                correlation_analysis = await self.orchestrator.correlation_engine.correlate_findings(
                    github_response.findings if github_response else None,
                    kubernetes_response.findings if kubernetes_response else None,
                    jenkins_response.findings if jenkins_response else None,  # ← ADD THIS PARAMETER
                    state["user_prompt"]
                )
            except Exception as e:
                print(f"⚠️ Correlation analysis failed: {str(e)}")
                correlation_analysis = None
        elif agent_count == 1:
            print("🧠 Single agent analysis - no correlation needed")
        else:
            print("🧠 No agent findings available for correlation")

        historical_solutions = None
        if self.orchestrator.rag_service:
            print("🔍 Searching for historical solutions...")
            context = self._create_rag_context(github_response, kubernetes_response, jenkins_response, state)
            historical_solutions = await self.orchestrator.rag_service.get_historical_solutions(
                state["user_prompt"], 
                context
            )
        
        # Extract findings
        github_findings = github_response.findings if github_response else None
        kubernetes_findings = kubernetes_response.findings if kubernetes_response else None
        jenkins_findings = jenkins_response.findings if jenkins_response else None
        
        try:
            # Generate developer-focused summary with RAG integration
            developer_summary = await self.orchestrator.summarizer.generate_correlated_summary(
                github_response, 
                kubernetes_response, 
                jenkins_response,
                correlation_analysis,  # ← PROPER VALUE, not None
                historical_solutions,  # ← PROPER VALUE, not None
                state
            )
            
            # Collect all actionable recommendations
            all_actions = []
            if github_response and github_response.next_actions:
                all_actions.extend(github_response.next_actions[:3])  
            if kubernetes_response and kubernetes_response.next_actions:
                all_actions.extend(kubernetes_response.next_actions[:3])  
            if jenkins_response and jenkins_response.next_actions:
                all_actions.extend(jenkins_response.next_actions[:3]) 
            
            # Add historical solution actions
            if historical_solutions and historical_solutions.get("solutions_found"):
                solutions = historical_solutions.get("recommended_solutions", [])
                for solution in solutions[:2]:  
                    solution_text = solution.get("solution", "")
                    jira_id = solution.get("jira_id", "")
                    if solution_text:
                        action_text = f"[{jira_id}] {solution_text[:100]}..."
                        all_actions.insert(0, action_text) 
            
            # Add correlation-based actions
            if correlation_analysis and correlation_analysis.get("actionable_solution"):
                all_actions.insert(0, correlation_analysis["actionable_solution"]) 
            
            final_response = await self._generate_final_standardized_response(
                github_response, 
                kubernetes_response, 
                jenkins_response, 
                correlation_analysis, 
                historical_solutions,
                all_actions,
                state
            )
            print(f"🔍 Final response inside: {final_response}")
            
            return {
                **state,
                "correlation_analysis": correlation_analysis,
                "historical_solutions": historical_solutions,
                "summary": developer_summary,
                "action_items": all_actions[:5],  
                "status": "completed",
                "final_response": final_response  
            }
            
        except Exception as e:
            print(f"❌ Intelligent summarizer failed: {e}")
            
            error_response = {
                "status": "failed",
                "problem_identified": "Analysis failed due to technical error",
                "root_cause": f"Technical error during analysis: {str(e)}",
                "solution": ["Contact DevOps team for manual analysis", "Retry the request"],
                "summary": f"Intelligent analysis failed: {str(e)}",
                "rag_solution": {
                    "rag_solution": None,
                    "similarity_score": 0.0,
                    "jira_id": None,
                    "message": "No RAG solution available due to analysis failure"
                },
                "confidence": False,
                "confidence_level": "low",
                "confidence_reasoning": "Analysis failed - no reliable results available"
            }
            
            return {
                **state,
                "summary": "Analysis completed with errors",
                "status": "completed_with_errors",
                "final_response": error_response  
            }

    def _create_rag_context(self, github_response, kubernetes_response, jenkins_response, state) -> Dict[str, Any]:
        """Create context for RAG service from current findings"""
        context = {}
        
        # Extract findings from AgentResponse objects if needed
        kubernetes_findings = kubernetes_response.findings if kubernetes_response else None
        github_findings = github_response.findings if github_response else None
        jenkins_findings = jenkins_response.findings if jenkins_response else None
        
        # Extract namespace and environment from Kubernetes findings
        if kubernetes_findings:
            context["namespace"] = kubernetes_findings.get("namespace")
            context["environment"] = kubernetes_findings.get("environment")
            
            # Extract services from unhealthy pods
            unhealthy_pods = kubernetes_findings.get("unhealthy_pods", [])
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
            root_causes = kubernetes_findings.get("root_causes", [])
            context["issue_type"] = kubernetes_findings.get("issue_type", "unknown")
            context["error_patterns"] = root_causes
        
        # Extract GitHub context
        if github_findings:
            failed_checks = github_findings.get("failed_checks", [])
            error_patterns = []
            for check in failed_checks:
                if check.get("details"):
                    error_patterns.append(check["details"])
            if error_patterns:
                context["error_patterns"] = context.get("error_patterns", []) + error_patterns
        
        # Extract Jenkins context
        if jenkins_findings:
            analysis = jenkins_findings.get("analysis", {})
            if analysis.get("error_details"):
                context["error_patterns"] = context.get("error_patterns", []) + analysis["error_details"]
        
        return context
    def _combine_k8s_findings(self, all_findings: list, namespace_info: dict) -> dict:
        """Combine findings from multiple namespaces into a single comprehensive result"""
        if not all_findings:
            return {
                "status": "success",
                "problem_identified": "No issues found in any namespace",
                "root_cause": "All namespaces are healthy",
                "solution": [],
                "summary": "All applications are running normally"
            }
        
        # Combine all findings
        combined_events = []
        combined_unhealthy_pods = []
        combined_healthy_pods = []
        combined_root_causes = []
        combined_immediate_actions = []
        combined_solutions = []
        
        # Track the most detailed analysis for problem identification
        most_detailed_findings = None
        total_unhealthy_pods = 0
        total_healthy_pods = 0
        total_events = 0
        has_issues = False
        
        for findings in all_findings:
            if findings:
                # Extract events (if available)
                events = findings.get("events", [])
                combined_events.extend(events)
                total_events += len(events)
                
                # Extract unhealthy pods (if available)
                unhealthy_pods = findings.get("unhealthy_pods", [])
                combined_unhealthy_pods.extend(unhealthy_pods)
                total_unhealthy_pods += len(unhealthy_pods)
                
                # Extract healthy pods (if available)
                healthy_pods = findings.get("healthy_pods", [])
                combined_healthy_pods.extend(healthy_pods)
                total_healthy_pods += len(healthy_pods)
                
                # Extract root causes (if available)
                root_causes = findings.get("root_causes", [])
                combined_root_causes.extend(root_causes)
                
                # Extract immediate actions (if available)
                immediate_actions = findings.get("immediate_actions", [])
                combined_immediate_actions.extend(immediate_actions)
                
                # Extract solutions (if available)
                solution = findings.get("solution", [])
                if solution:
                    combined_solutions.extend(solution)
                
                # SIMPLIFIED: Check for ANY intelligent analysis or issues
                intelligent_analysis = findings.get("intelligent_analysis", {})
                problem_identified = findings.get("problem_identified", "")
                root_cause = findings.get("root_cause", "")
                
                # If we have intelligent analysis, use it
                if intelligent_analysis:
                    has_issues = True
                    most_detailed_findings = findings  # Always prioritize intelligent analysis
                # Or if there are unhealthy pods
                elif unhealthy_pods and len(unhealthy_pods) > 0:
                    has_issues = True
                    if not most_detailed_findings:
                        most_detailed_findings = findings
                # Or if there are explicit problem identifications
                elif problem_identified or root_cause:
                    has_issues = True
                    if not most_detailed_findings:
                        most_detailed_findings = findings
        
        # Determine overall status based on actual findings
        if has_issues or total_unhealthy_pods > 0 or combined_root_causes:
            status = "issues_found"
            
            # Use the most detailed findings for problem identification
            if most_detailed_findings:
                # PRIORITY 1: Use intelligent analysis if available
                intelligent_analysis = most_detailed_findings.get('intelligent_analysis', {})
                if intelligent_analysis:
                    problem_identified = intelligent_analysis.get('problem_summary', '')
                    root_cause = intelligent_analysis.get('root_cause', '')
                    
                    # If intelligent analysis is empty, don't use fallback - something is wrong
                    if not problem_identified:
                        problem_identified = "Intelligent analysis available but problem summary missing"
                    if not root_cause:
                        root_cause = "Intelligent analysis available but root cause missing"
                else:
                    # PRIORITY 2: Use explicit problem/root cause fields
                    problem_identified = most_detailed_findings.get("problem_identified", "")
                    root_cause = most_detailed_findings.get("root_cause", "")
                    
                    # ONLY use generic fallback if nothing else is available
                    if not problem_identified and not root_cause:
                        problem_identified = f"Issues detected in namespace analysis"
                        root_cause = f"Multiple indicators suggest problems in {len(all_findings)} namespaces"
            else:
                problem_identified = f"Issues detected but no detailed analysis available"
                root_cause = f"Analysis indicates problems across {len(all_findings)} namespaces"
        else:
            status = "healthy"
            problem_identified = "All namespaces are healthy"
            root_cause = "No issues detected"
        
        # Create comprehensive summary without hardcoded text
        summary_parts = []
        if intelligent_analysis := most_detailed_findings.get('intelligent_analysis', {}) if most_detailed_findings else {}:
            # Use intelligent summary if available
            summary = intelligent_analysis.get('problem_summary', '')
            if not summary:
                summary = f"AI Analysis: {problem_identified}"
        else:
            # Build summary from actual findings
            if total_unhealthy_pods > 0:
                summary_parts.append(f"Found {total_unhealthy_pods} unhealthy pods")
            if combined_root_causes:
                summary_parts.append(f"Identified {len(combined_root_causes)} root causes")
            if total_events > 0:
                summary_parts.append(f"Analyzed {total_events} events")
            
            summary = "; ".join(summary_parts) if summary_parts else "All applications are running normally"
        
        # Determine the best solution to use
        final_solution = []
        if combined_solutions:
            # Use the actual solutions from individual findings
            final_solution = combined_solutions[:5]  # Limit to top 5
        elif combined_immediate_actions:
            # Fallback to immediate actions if no solutions available
            final_solution = combined_immediate_actions[:5]
        else:
            # Last resort - generate basic solutions
            final_solution = ["Review pod status and events", "Check application logs", "Verify configuration"]
        
        # Preserve the intelligent analysis in the final result
        result = {
            "status": status,
            "problem_identified": problem_identified,
            "root_cause": root_cause,
            "solution": final_solution,
            "summary": summary,
            "events": combined_events,
            "unhealthy_pods": combined_unhealthy_pods,
            "healthy_pods": combined_healthy_pods,
            "root_causes": combined_root_causes,
            "immediate_actions": combined_immediate_actions,
            "namespaces_analyzed": namespace_info.get("namespaces", []),
            "environment": namespace_info.get("environment", "unknown"),
            "business_unit": namespace_info.get("business_unit", "unknown")
        }
        
        # CRITICAL: Preserve intelligent analysis and RAG solution in the result
        if most_detailed_findings and most_detailed_findings.get('intelligent_analysis'):
            result['intelligent_analysis'] = most_detailed_findings['intelligent_analysis']
        
        # Preserve RAG solution from the most detailed findings
        if most_detailed_findings and most_detailed_findings.get('rag_solution'):
            result['rag_solution'] = most_detailed_findings['rag_solution']
        else:
            # Default RAG solution if none available
            result['rag_solution'] = {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "No RAG solution available"
            }
        
        return result
    
    async def unavailable_agent_node(self, state: DevOpsWorkflowState) -> DevOpsWorkflowState:
        """Handle requests that don't require DevOps agent analysis"""
        
        print("Unavailable Agent: No agent present for this")
        final_response = {
            "status": "unsupported",
            "problem_identified": "Request not supported for automated analysis",
            "root_cause": "The user's request does not fall into a category that can be analyzed by the available DevOps agents.",
            "solution": ["Please rephrase your request if it is a DevOps issue that requires analysis, or handle it manually."],
            "summary": "The provided request is not an analysis task and is therefore not supported by this automated system.",
            "rag_solution": {
                "solutions_found": False,
                "message": "No RAG solution available as the request is unsupported."
            },
            "confidence": False,
            "confidence_level": "low",
            "confidence_reasoning": "The request was correctly routed to the unavailable agent, as it is outside the scope of automated analysis."
        }
        
        return {
            **state,
            "unavailable_response": AgentResponse(
                agent_name="Unavailable Agent",
                status="unsupported",
                findings={"request_type": "unsupported", "message": "This request does not match any supported DevOps analysis patterns."},
                next_actions=["This request does not match any supported DevOps analysis patterns."]
            ),
            "agent_status": {**state.get("agent_status", {}), "unavailable": "completed"},
            "status": "unsupported",
            "final_response": final_response  
        }

    async def _generate_final_standardized_response(self, github_response, kubernetes_response, jenkins_response, correlation_analysis, historical_solutions, all_actions, state) -> Dict[str, Any]:
        """Generate the final standardized JSON response using LLM analysis of all findings"""
        
        confidence = True
        confidence_level = "high"
        confidence_reasoning = "Comprehensive analysis performed"
        
        agent_count = sum([
            1 if github_response and github_response.findings else 0,
            1 if kubernetes_response and kubernetes_response.findings else 0,
            1 if jenkins_response and jenkins_response.findings else 0
        ])
        
        if agent_count == 0:
            confidence = False
            confidence_level = "low"
            confidence_reasoning = "No agents were able to analyze this request"
        elif agent_count == 1:
            confidence = True
            confidence_level = "medium"
            confidence_reasoning = "Single agent provided analysis for this query"
        elif agent_count >= 2:
            confidence = True
            confidence_level = "high"
            confidence_reasoning = "Multiple agents provided comprehensive analysis"
        
        try:
            final_response = await self._llm_generate_final_response(
                github_response, 
                kubernetes_response, 
                jenkins_response, 
                correlation_analysis, 
                historical_solutions,
                all_actions,
                confidence,
                confidence_level,
                confidence_reasoning
            )
            return final_response
            
        except Exception as e:
            print(f"❌ LLM final response generation failed: {str(e)}")
            
            return {
                "status": "success",
                "problem_identified": "Analysis completed but synthesis failed",
                "root_cause": f"LLM synthesis error: {str(e)}",
                "solution": all_actions[:5] if all_actions else ["Manual review required"],
                "summary": f"Analysis completed with {agent_count} agents but final synthesis failed",
                "rag_solution": historical_solutions,
                "confidence": confidence,
                "confidence_level": confidence_level,
                "confidence_reasoning": confidence_reasoning
            }

    async def _llm_generate_final_response(self, github_response, kubernetes_response, jenkins_response, correlation_analysis, historical_solutions, all_actions, confidence, confidence_level, confidence_reasoning) -> Dict[str, Any]:
        """Use LLM to intelligently synthesize all findings into final response"""
        
        github_findings = github_response.findings if github_response else None
        kubernetes_findings = kubernetes_response.findings if kubernetes_response else None
        jenkins_findings = jenkins_response.findings if jenkins_response else None
        
        final_response_prompt = ChatPromptTemplate.from_template(
            FINAL_RESPONSE_SYSTEM_PROMPT + "\n\n" + FINAL_RESPONSE_USER_PROMPT_TEMPLATE
        )
        
        try:
            final_response_chain = final_response_prompt | self.orchestrator.services.llm
            
            response = await final_response_chain.ainvoke({
                "github_findings": str(github_findings) if github_findings else "No GitHub analysis performed",
                "kubernetes_findings": str(kubernetes_findings) if kubernetes_findings else "No Kubernetes analysis performed", 
                "jenkins_findings": str(jenkins_findings) if jenkins_findings else "No Jenkins analysis performed",
                "correlation_analysis": str(correlation_analysis) if correlation_analysis else "No correlation analysis performed",
                "historical_solutions": str(historical_solutions) if historical_solutions else "No historical solutions found",
                "all_actions": str(all_actions) if all_actions else "No specific actions recommended"
            })
            
            content = response.content.strip()
            json_content = content
            if "```json" in content:
                import re
                json_content = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_content:
                    json_content = json_content.group(1)
            
            import json
            llm_response = json.loads(json_content)
            
            llm_response["rag_solution"] = historical_solutions
            llm_response["confidence"] = confidence
            llm_response["confidence_level"] = confidence_level
            llm_response["confidence_reasoning"] = confidence_reasoning
            
            return llm_response
            
        except Exception as e:
            print(f"❌ Failed to generate or parse LLM final response: {str(e)}")
            print(f"❌ Raw LLM response: {response.content if 'response' in locals() else 'No response'}")
            
            return {
                "status": "success",
                "problem_identified": "Analysis completed but response parsing failed",
                "root_cause": "LLM response parsing error",
                "solution": all_actions[:5] if all_actions else ["Manual review required"],
                "summary": "Analysis completed but final response synthesis failed",
                "rag_solution": historical_solutions,
                "confidence": confidence,
                "confidence_level": confidence_level,
                "confidence_reasoning": confidence_reasoning
            }
