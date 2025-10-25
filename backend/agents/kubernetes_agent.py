"""
Kubernetes Debugging Agent
This agent is responsible for diagnosing issues within a Kubernetes cluster.
It follows a systematic, multi-step debugging process that mirrors
what an experienced DevOps engineer would do.
"""
import json
from typing import List, Dict, Any

from langchain_openai import AzureChatOpenAI

# Import from the new modular structure
from ..utils.logging import ToolCallLogger
from ..utils.detectors import namespace_detector
from ..utils.parsers import parse_k8s_yaml_output
from ..utils.detectors import SmartContainerDetector
from ..utils.confidence_detector import ConfidenceDetector
from ..prompts.kubernetes import KUBERNETES_SYSTEM_PROMPT, KUBERNETES_ANALYSIS_PROMPT_TEMPLATE, get_no_logs_container_analysis_prompt, get_kubernetes_analysis_prompt, get_generic_container_analysis_prompt, get_kubernetes_chain_of_thought_prompt, get_intelligent_log_analyzer_prompt
class PerfectedKubernetesDebugger:
    """Perfected Kubernetes debugging with focused analysis on unhealthy pods only"""
    
    def __init__(self, kubernetes_tools: List, tool_logger: ToolCallLogger, llm: AzureChatOpenAI, rag_service=None):
        self.k8s_tools = kubernetes_tools
        self.logger = tool_logger
        self.tool_call_counter = 0
        self.llm = llm
        self.rag_service = rag_service
    
    async def debug_application_health(self, namespace: str, environment: str, business_unit: str) -> Dict[str, Any]:
        """Follow systematic DevOps debugging steps - PERFECTED VERSION"""
        
        findings = {
            "namespace": namespace,
            "environment": environment,
            "business_unit": business_unit,
            "debug_steps": [],
            "pod_status": {},
            "unhealthy_pods": [],
            "healthy_pods": [],
            "events": [],
            "logs": {},
            "resource_usage": {},
            "root_causes": [],
            "immediate_actions": [],
            "detailed_analysis": "",
            "confidence": "high"
        }
        
        # Extract app name from namespace for smart container detection
        app_name = namespace.replace(f"{environment}-", "") if f"{environment}-" in namespace else namespace
        
        self.logger.log_analysis_step(
            "1. NAMESPACE VERIFICATION", 
            f"Checking if namespace '{namespace}' exists and is healthy"
        )
        
        # Step 1: Get namespace info and pods
        findings["debug_steps"].append("Step 1: Namespace and Pod Discovery")
        pod_data = await self._get_pods_in_namespace(namespace)
        findings["pod_status"] = pod_data
        
        if not pod_data.get("pods"):
            findings["root_causes"].append(f"No pods found in namespace '{namespace}' - namespace may not exist or be empty")
            findings["immediate_actions"].append(f"Verify namespace '{namespace}' exists and has deployments")
            # Convert to standardized format before returning
            return self._convert_to_standardized_format(findings)
        
        # Step 2: SMART Pod Health Analysis - Categorize pods
        self.logger.log_analysis_step(
            "2. SMART POD HEALTH ANALYSIS", 
            f"Categorizing {len(pod_data.get('pods', []))} pods by health status"
        )
        findings["debug_steps"].append("Step 2: Smart Pod Health Analysis")
        
        for pod in pod_data.get("pods", []):
            pod_name = pod.get("metadata", {}).get("name", "unknown")
            if pod_name.startswith("pre-install-pre-upgrade"):
                print("Not considering pre-install-pre-upgrade")
                continue
            status = pod.get("status", {})
            phase = status.get("phase", "Unknown")
            
            pod_info = {
                "name": pod_name,
                "phase": phase,
                "reason": status.get("reason", "Unknown"),
                "conditions": status.get("conditions", []),
                "container_statuses": status.get("containerStatuses", []),
                "restart_count": self._get_total_restart_count(status),
                "ready": self._is_pod_ready(status),
                "pod_data": pod  # Keep full pod data for container detection
            }
            
            if phase not in ["Running", "Succeeded"] or not pod_info["ready"] or pod_info["restart_count"] > 3:
                findings["unhealthy_pods"].append(pod_info)
            else:
                findings["healthy_pods"].append(pod_info)
        
        print(f"   📊 Pod Health Summary:")
        print(f"      • Healthy Pods: {len(findings['healthy_pods'])}")
        print(f"      • Unhealthy Pods: {len(findings['unhealthy_pods'])}")
        
        if findings["unhealthy_pods"]:
            findings["root_causes"].append(f"Found {len(findings['unhealthy_pods'])} unhealthy pods in {namespace}")
            for pod in findings["unhealthy_pods"]:
                status_desc = f"{pod['phase']}"
                if pod['restart_count'] > 0:
                    status_desc += f" (restarts: {pod['restart_count']})"
                findings["immediate_actions"].append(f"Investigate pod {pod['name']} - Status: {status_desc}")
        
        # Step 3: Get events for the namespace
        self.logger.log_analysis_step(
            "3. KUBERNETES EVENTS ANALYSIS", 
            f"Fetching cluster events for namespace '{namespace}'"
        )
        findings["debug_steps"].append("Step 3: Kubernetes Events Analysis")
        
        events_data = await self._get_events_for_namespace(namespace)
        findings["events"] = events_data.get("events", [])
        
        # Analyze events for root causes
        warning_events = [e for e in findings["events"] if e.get("type") == "Warning"]
        if warning_events:
            print(f"   ⚠️ Found {len(warning_events)} warning events")
            for event in warning_events[:5]:  # Top 5 warning events
                reason = event.get("reason", "Unknown")
                message = event.get("message", "")
                event_object = event.get("involvedObject", {}).get("name", event.get("object", "unknown"))
                
                if "BackOff" in reason or "CrashLoopBackOff" in reason:
                    findings["root_causes"].append(f"Container restart loop detected: {reason} in {event_object}")
                    findings["immediate_actions"].append(f"Check container logs for {event_object}")
                elif "Unhealthy" in reason:
                    findings["root_causes"].append(f"Health probe failure: {message[:100]} in {event_object}")
                    findings["immediate_actions"].append("Review readiness/liveness probe configuration")
                elif "Failed" in reason and "pull" in message.lower():
                    findings["root_causes"].append(f"Image pull failure: {message[:100]}")
                    findings["immediate_actions"].extend([
                        "Verify the container image exists in the registry",
                        "Check registry credentials and access permissions", 
                        "Validate the image tag/version is correct",
                        "Ensure the image registry URL is accessible from the cluster",
                        "Check if image pull secrets are configured correctly"
                    ])
                elif "Failed" in reason and ("secret" in message.lower() or "configmap" in message.lower()):
                    findings["root_causes"].append(f"Secret/Config missing: {message[:100]}")
                    findings["immediate_actions"].append("Create missing secrets or configmaps")
                elif "Failed" in reason:
                    findings["root_causes"].append(f"Resource failure: {reason} - {message[:100]}")
        
        # Step 4: FOCUSED Container Log Analysis - ONLY for unhealthy pods
        # if findings["unhealthy_pods"]:
        #     self.logger.log_analysis_step(
        #         "4. FOCUSED CONTAINER LOG ANALYSIS", 
        #         f"Fetching logs from {len(findings['unhealthy_pods'])} unhealthy pods ONLY"
        #     )
        #     findings["debug_steps"].append("Step 4: Focused Container Log Analysis")
            
        #     for pod_info in findings["unhealthy_pods"][:3]:  # Max 3 unhealthy pods to avoid spam
        #         pod_name = pod_info["name"]
        #         pod_data = pod_info["pod_data"]
                
        #         # Smart container detection
        #         main_container = SmartContainerDetector.detect_main_container(pod_data, app_name)
        #         log_data = await self._get_pod_logs_smart(namespace, pod_name, main_container)

        #         print(f"   🎯 Detected main container for {pod_name}: {main_container}")
        #         print(f"   🎯 pod_data: {pod_data}")
        #         print(f"   🎯 app_name: {app_name}")
        #         print(f"   🎯 main_container: {main_container}")
        #         print(f"   🎯 namespace: {namespace}")
        #         print(f"   🎯 pod_name: {pod_name}")
        #         print(f"   🎯 log_data: {log_data}")
        #         print(f"   🎯 findings: {findings}")
        #         # Try to get logs from main container first
        #         print("Have reached here just before the log data")
        #         findings["logs"][pod_name] = log_data
                
        #         # Analyze logs for common error patterns
        #         # self._analyze_container_logs(log_data, pod_name, findings)
        #         await self._analyze_container_logs_intelligent(log_data, pod_data, findings["events"], pod_name, findings)
        if findings["unhealthy_pods"]:
            self.logger.log_analysis_step(
                "4. INTELLIGENT CONTAINER LOG ANALYSIS", 
                f"AI-powered analysis of {len(findings['unhealthy_pods'])} unhealthy pods"
            )
            findings["debug_steps"].append("Step 4: Intelligent Container Log Analysis")
            
            for pod_info in findings["unhealthy_pods"][:3]:  # Max 3 unhealthy pods
                pod_name = pod_info["name"]
                pod_data = pod_info["pod_data"]
                
                # Smart container detection
                main_container = SmartContainerDetector.detect_main_container(pod_data, app_name)
                log_data = await self._get_pod_logs_smart(namespace, pod_name, main_container)
                
                findings["logs"][pod_name] = log_data
                
                # Use intelligent analysis instead of basic pattern matching
                await self._analyze_container_logs_intelligent(log_data, pod_data, findings["events"], pod_name, findings)
        
        else:
            print(f"   ✅ All pods are healthy - skipping log analysis")
        
        # Generate detailed analysis
        # findings["detailed_analysis"] = self._generate_detailed_analysis(findings)
        findings["detailed_analysis"] = self._generate_intelligent_analysis(findings)
        
        # Convert to standardized format with RAG solution
        return await self._convert_to_standardized_format_with_rag(findings)
    
    def _get_total_restart_count(self, pod_status: Dict[str, Any]) -> int:
        """Get total restart count across all containers"""
        total_restarts = 0
        container_statuses = pod_status.get("containerStatuses", [])
        for container in container_statuses:
            total_restarts += container.get("restartCount", 0)
        return total_restarts
    
    def _is_pod_ready(self, pod_status: Dict[str, Any]) -> bool:
        """Check if pod is ready"""
        conditions = pod_status.get("conditions", [])
        for condition in conditions:
            if condition.get("type") == "Ready":
                return condition.get("status") == "True"
        return False
    
    async def _get_pods_in_namespace(self, namespace: str) -> Dict[str, Any]:
        """Get pods in specific namespace with streaming"""
        self.tool_call_counter += 1
        
        pods_tool = next((t for t in self.k8s_tools if t.name == "pods_list_in_namespace"), None)
        if not pods_tool:
            return {"error": "pods_list_in_namespace tool not available", "pods": []}
        
        self.logger.log_tool_call("pods_list_in_namespace", {"namespace": namespace}, self.tool_call_counter)
        
        try:
            # FIXED: Use direct tool invocation instead of client.call_tool
            pods_yaml = await pods_tool.ainvoke({"namespace": namespace})
            pods_data = parse_k8s_yaml_output(pods_yaml)
            
            result_summary = f"Found {len(pods_data)} pods in namespace '{namespace}'"
            self.logger.log_tool_result("pods_list_in_namespace", result_summary, self.tool_call_counter)
            
            return {"pods": pods_data, "namespace": namespace, "count": len(pods_data)}
            
        except Exception as e:
            error_msg = f"Failed to get pods in {namespace}: {str(e)}"
            self.logger.log_tool_result("pods_list_in_namespace", f"ERROR: {error_msg}", self.tool_call_counter)
            return {"error": error_msg, "pods": [], "namespace": namespace}
    
    async def _get_events_for_namespace(self, namespace: str) -> Dict[str, Any]:
        """Get events for specific namespace"""
        self.tool_call_counter += 1
        
        events_tool = next((t for t in self.k8s_tools if t.name == "events_list"), None)
        if not events_tool:
            return {"error": "events_list tool not available", "events": []}
        
        self.logger.log_tool_call("events_list", {}, self.tool_call_counter)
        
        try:
            # FIXED: Use direct tool invocation
            events_raw = await events_tool.ainvoke({})
            all_events = parse_k8s_yaml_output(events_raw)
            
            # Filter events for this namespace
            namespace_events = []
            for event in all_events:
                event_ns = event.get("namespace")
                if not event_ns and event.get("involvedObject"):
                    event_ns = event["involvedObject"].get("namespace")
                
                if event_ns and event_ns.lower() == namespace.lower():
                    namespace_events.append(event)
            
            result_summary = f"Found {len(namespace_events)} events for namespace '{namespace}' (filtered from {len(all_events)} total)"
            self.logger.log_tool_result("events_list", result_summary, self.tool_call_counter)
            
            return {"events": namespace_events, "namespace": namespace, "total_events": len(all_events)}
            
        except Exception as e:
            error_msg = f"Failed to get events: {str(e)}"
            self.logger.log_tool_result("events_list", f"ERROR: {error_msg}", self.tool_call_counter)
            return {"error": error_msg, "events": []}
    
    async def _get_pod_logs_smart(self, namespace: str, pod_name: str, container_name: str) -> Dict[str, Any]:
        """Get logs from specific pod with smart container selection and better error handling"""
        self.tool_call_counter += 1
        print("Inside the get_pod_logs_smart")
        logs_tool = next((t for t in self.k8s_tools if t.name == "pods_log"), None)
        for tool in self.k8s_tools:
            print(f"tool: {tool.name}")
        if not logs_tool:
            return {"error": "pods_log tool not available", "success": False}
        
        # Try with specific container first
        self.logger.log_tool_call("pods_log", {
            "namespace": namespace, 
            "name": pod_name, 
            "container": container_name
        }, self.tool_call_counter)
        
        try:
            # FIXED: Use direct tool invocation with better error handling
            logs_content = await logs_tool.ainvoke({
                "namespace": namespace, 
                "name": pod_name, 
                "container": container_name
            })
            
            if isinstance(logs_content, str) and logs_content and "CreateContainerConfigError" not in logs_content:
                log_lines = logs_content.split('\n')
                result_summary = f"Retrieved {len(log_lines)} log lines from pod '{pod_name}' container '{container_name}'"
                self.logger.log_tool_result("pods_log", result_summary, self.tool_call_counter)
                
                return {
                    "logs": logs_content, 
                    "pod": pod_name, 
                    "container": container_name,
                    "namespace": namespace,
                    "success": True
                }
        except Exception as container_error:
            return {
            "error": f"Cannot get logs for pod {pod_name}. Reason: {str(container_error)}",
            "reason": "container_config_error" if "CreateContainerConfigError" in str(container_error) else "unknown",
            "success": False
            }
        
        # If container-specific fails or has config errors, try without container parameter
        print(f"   ⚠️ Container-specific log failed, trying default container...")
        try:
            logs_content = await logs_tool.ainvoke({"namespace": namespace, "name": pod_name})
            
            if isinstance(logs_content, str) and logs_content and "CreateContainerConfigError" not in logs_content:
                log_lines = logs_content.split('\n')
                result_summary = f"Retrieved {len(log_lines)} log lines from pod '{pod_name}' (default container)"
                self.logger.log_tool_result("pods_log", result_summary, self.tool_call_counter)
                
                return {
                    "logs": logs_content, 
                    "pod": pod_name, 
                    "container": "default",
                    "namespace": namespace,
                    "success": True
                }
        except Exception as default_error:
            pass
        
        # If both fail, return meaningful error
        error_msg = f"Pod {pod_name} cannot provide logs - likely in CreateContainerConfigError state (missing secrets/config)"
        self.logger.log_tool_result("pods_log", f"INFO: {error_msg}", self.tool_call_counter)
        
        return {
            "error": error_msg, 
            "pod": pod_name, 
            "container": container_name,
            "success": False,
            "reason": "container_config_error"
        }
    
    def _analyze_container_logs(self, log_data: Dict[str, Any], pod_name: str, findings: Dict[str, Any]):
        """Analyze container logs for common error patterns"""
        if not log_data.get("logs") or not log_data.get("success"):
            # If logs failed due to config error, add specific root cause
            if log_data.get("reason") == "container_config_error":
                findings["root_causes"].append(f"Pod {pod_name} has container configuration errors (likely missing secrets/configmaps)")
                findings["immediate_actions"].append(f"Check secrets and configmaps required by {pod_name}")
            return
        
        log_content = log_data["logs"].lower()
        
        # Pattern matching for common issues
        if "out of memory" in log_content or "oom killed" in log_content or "oom" in log_content:
            findings["root_causes"].append(f"Pod {pod_name} experiencing OOM (Out of Memory)")
            findings["immediate_actions"].append(f"Increase memory limits for {pod_name}")
        
        if "connection refused" in log_content or "connection reset" in log_content:
            findings["root_causes"].append(f"Pod {pod_name} has connection issues")
            findings["immediate_actions"].append(f"Check network connectivity for {pod_name}")
        
        if "timeout" in log_content and "error" in log_content:
            findings["root_causes"].append(f"Pod {pod_name} experiencing timeout errors")
            findings["immediate_actions"].append(f"Review timeout configurations for {pod_name}")
        
        if "permission denied" in log_content or "access denied" in log_content:
            findings["root_causes"].append(f"Pod {pod_name} has permission issues")
            findings["immediate_actions"].append(f"Check RBAC and service account permissions for {pod_name}")
        
        if "panic" in log_content or "fatal" in log_content:
            findings["root_causes"].append(f"Pod {pod_name} experiencing application crashes")
            findings["immediate_actions"].append(f"Review application code and error handling for {pod_name}")
        
        if "no space left" in log_content or "disk full" in log_content:
            findings["root_causes"].append(f"Pod {pod_name} experiencing disk space issues")
            findings["immediate_actions"].append(f"Check disk usage and clean up or increase storage for {pod_name}")
    
    async def _analyze_container_logs_intelligent(self, log_data: Dict[str, Any], pod_data: Dict[str, Any], events: List[Dict], pod_name: str, findings: Dict[str, Any]):
        """Generic intelligent analysis using LLM with chain-of-thought reasoning"""
        
        waiting_reason = ""
        for st in pod_data.get("status", {}).get("containerStatuses", []):
            waiting_reason = (st.get("state", {}).get("waiting", {}) or {}).get("reason", waiting_reason)


        if not log_data.get("success") or waiting_reason in ["CreateContainerConfigError", "ImagePullBackOff", "ErrImagePull", "InvalidImageName"]:
            pod_events = [e for e in events if e.get("involvedObject", {}).get("name") == pod_name]
            
            prompt = get_no_logs_container_analysis_prompt(pod_data, pod_events)
            try:
                response = await self.llm.ainvoke(prompt)
                content = (response.content or "").strip()
                if content.startswith("```json"): content = content[7:]
                if content.startswith("```"): content = content[3:]
                if content.endswith("```"): content = content[:-3]
                content = content.strip()
                analysis = json.loads(content)

                findings["intelligent_analysis"] = analysis
                findings["problem_summary"] = analysis.get("problem_summary", "Issue detected")
                findings["root_cause"] = analysis.get("root_cause", "Under investigation")
                findings["developer_actions"] = analysis.get("developer_actions", [])
                findings["prevention"] = analysis.get("prevention", "")
                findings["root_causes"].append(findings["root_cause"])
                findings["immediate_actions"].extend(findings["developer_actions"])
                return
            except Exception as e:
                print(f"❌ No-logs intelligent analysis failed: {e}")
                self._analyze_container_logs_basic(log_data, pod_name, findings)
                return        
        # Extract relevant information for generic analysis
        pod_spec = pod_data.get("spec", {})
        containers = pod_spec.get("containers", [])
        main_container = containers[0] if containers else {}
        
        # Prepare data for generic container analysis
        container_config = {
            "image": main_container.get("image", "unknown"),
            "resources": main_container.get("resources", {}),
            "env": main_container.get("env", [])
        }
        
        port_config = {
            "container_ports": main_container.get("ports", []),
            "service_ports": "extracted from service if available"
        }
        
        health_config = {
            "liveness_probe": main_container.get("livenessProbe", {}),
            "readiness_probe": main_container.get("readinessProbe", {})
        }
        
        # Filter relevant events for this pod
        pod_events = [e for e in events if e.get("involvedObject", {}).get("name") == pod_name]
        
        # Use generic container analysis prompt
        analysis_prompt = get_generic_container_analysis_prompt(
            log_data["logs"], 
            container_config, 
            port_config, 
            health_config, 
            pod_events
        )
    
        try:
            response = await self.llm.ainvoke(analysis_prompt)
            content = response.content.strip()
            print(f"🔍 DEBUG: LLM Response: {content[:500]}...")

            # Clean JSON if needed
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            print(f"🔍 DEBUG: Cleaned content: {content[:200]}...")

            analysis = json.loads(content)
            print(f"🔍 DEBUG: Parsed analysis: {analysis}")

            # Add findings
            findings["intelligent_analysis"] = analysis
            findings["root_causes"].append(analysis["root_cause"])
            findings["immediate_actions"].extend(analysis["developer_actions"])
            findings["problem_summary"] = analysis.get("problem_summary", "Issue detected")
            findings["prevention"] = analysis.get("prevention", "Review configurations regularly")
            findings["root_cause"] = analysis["root_cause"]  # Single root cause for summary
            findings["developer_actions"] = analysis["developer_actions"]  # Actions for summary
            

        except Exception as e:
            print(f"❌ Intelligent analysis failed: {e}")
            print(f"🔍 DEBUG: Raw response: {response.content if 'response' in locals() else 'No response'}")

            # Fallback to basic analysis
            self._analyze_container_logs_basic(log_data, pod_name, findings)

    def _analyze_container_logs_basic(self, log_data: Dict[str, Any], pod_name: str, findings: Dict[str, Any]):
        """Fallback basic analysis - same as your original _analyze_container_logs"""
        if not log_data.get("logs") or not log_data.get("success"):
            return
        
        log_content = log_data["logs"].lower()
        
        # Basic pattern matching as fallback
        if "out of memory" in log_content or "oom killed" in log_content:
            findings["root_causes"].append(f"Pod {pod_name} experiencing OOM (Out of Memory)")
            findings["immediate_actions"].append(f"Increase memory limits for {pod_name}")
        
        if "connection refused" in log_content:
            findings["root_causes"].append(f"Pod {pod_name} has connection issues")
            findings["immediate_actions"].append(f"Check network connectivity for {pod_name}")
        
        # Add other basic patterns...

    async def _intelligent_pod_analysis(self, pod_data, events, logs):
        """Generic pod analysis using LLM instead of hardcoded patterns"""
        print("DEBUG LOGS: {}".format(logs))
        prompt = get_kubernetes_chain_of_thought_prompt(pod_data, events, logs)
        
        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Clean JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            return json.loads(content)
        except Exception as e:
            print(f"❌ Intelligent pod analysis failed: {e}")
            return {
                "reasoning_chain": ["Analysis failed"],
                "problem_summary": "Unable to analyze",
                "root_cause": "Analysis error",
                "developer_actions": ["Manual investigation required"],
                "confidence_level": "low"
            }

   
    def _generate_intelligent_analysis(self, findings: Dict[str, Any]) -> str:
        """Generate intelligent analysis summary"""
        if findings.get("intelligent_analysis"):
            analysis = findings["intelligent_analysis"]
            
            summary = f"""
            🔍 **PROBLEM**: {analysis.get('problem_summary', 'Issue detected')}

            🎯 **ROOT CAUSE**: {analysis.get('root_cause', 'Under investigation')}

            🧠 **AI REASONING**:
            """
            for i, step in enumerate(analysis.get('thinking_steps', []), 1):
                summary += f"   {i}. {step}\n"

            summary += f"""
            ⚡ **IMMEDIATE ACTIONS**:
            """
            for i, action in enumerate(analysis.get('developer_actions', []), 1):
                summary += f"   {i}. {action}\n"
            
            summary += f"""
            ✅ **PREVENTION**: {analysis.get('prevention', 'Review configurations regularly')}

            🎯 **CONFIDENCE**: {analysis.get('confidence_level', 'medium').upper()}
            """
            return summary
        else:
            # return self._generate_detailed_analysis(findings)
            return f"""
            🔍 **PROBLEM**: Analysis in progress
            🎯 **ROOT CAUSE**: Under investigation
            ⚡ **ACTIONS**: Check logs and pod status
            """

    def _generate_developer_summary(self, findings: Dict[str, Any]) -> str:
        """Generate concise, actionable summary for developers"""
        
        summary = f"""
            🔍 **PROBLEM**: {findings.get('problem_summary', 'Issue detected')}

            🎯 **ROOT CAUSE**: {findings.get('root_cause', 'Under investigation')}

            ⚡ **IMMEDIATE ACTIONS**:
            """
        
        for i, action in enumerate(findings.get('developer_actions', []), 1):
            summary += f"{i}. {action}\n"
        
        summary += f"""
        ✅ **VERIFICATION**: {findings.get('verification_steps', 'Check pod status after changes')}

        🛡️ **PREVENTION**: {findings.get('prevention', 'Monitor and review configurations')}
        """
        
        return summary

    def _detect_missing_resource(self, pod_data: Dict[str, Any], events: List[Dict]) -> str:
        """Detect missing resource from pod spec and events"""
        # Check volumes for missing config
        for volume in pod_data.get("spec", {}).get("volumes", []):
            if volume.get("secret") and "not found" in str(events):
                return "secret"
            if volume.get("configMap") and "not found" in str(events):
                return "configmap"
        
        # Check environment variables
        for container in pod_data.get("spec", {}).get("containers", []):
            for env in container.get("env", []):
                if env.get("valueFrom", {}).get("secretKeyRef") and "not found" in str(events):
                    return "secret"
        
        return "secrets or configmaps"
    
    def _convert_to_standardized_format(self, findings: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Kubernetes findings to standardized format - ONLY return required fields"""
        
        # Extract key information
        unhealthy_pods = findings.get("unhealthy_pods", [])
        root_causes = findings.get("root_causes", [])
        immediate_actions = findings.get("immediate_actions", [])
        
        # Get namespace for display
        namespace = findings.get('namespace', 'unknown')
        
        # Determine problem identification
        if not unhealthy_pods and not root_causes:
            problem_identified = "All pods are healthy"
            root_cause = "No issues detected"
            solution = ["Continue monitoring", "No immediate action required"]
            summary = "Kubernetes cluster is healthy with no pod issues"
        else:
            if not unhealthy_pods and root_causes:
                problem_identified = f"Namespace '{namespace}' has configuration or resource issues"
            else:
                problem_identified = f"Found {len(unhealthy_pods)} unhealthy pods in namespace '{namespace}'"
            
            root_cause = "; ".join(root_causes) if root_causes else "Pod health issues detected"
            solution = immediate_actions[:5] if immediate_actions else ["Investigate pod logs", "Check resource limits"]
            summary = f"Kubernetes namespace '{namespace}' has issues requiring attention: {root_cause}"
        
        # Return ONLY the standardized format fields
        return {
            "status": "success",
            "problem_identified": problem_identified,
            "root_cause": root_cause,
            "solution": solution,
            "summary": summary
        }
    
    async def _convert_to_standardized_format_with_rag(self, findings: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Kubernetes findings to standardized format with RAG solution"""
        
        # Extract key information
        unhealthy_pods = findings.get("unhealthy_pods", [])
        root_causes = findings.get("root_causes", [])
        immediate_actions = findings.get("immediate_actions", [])
        
        # Get namespace for display
        namespace = findings.get('namespace', 'unknown')
        
        # Determine problem identification
        intelligent_analysis = findings.get("intelligent_analysis")
        
        # Use intelligent analysis if available, otherwise fallback
        if intelligent_analysis:
            problem_identified = intelligent_analysis.get("problem_summary", f"Found {len(unhealthy_pods)} unhealthy pods in namespace '{namespace}'")
            root_cause = intelligent_analysis.get("root_cause", "Under investigation")
            
            # Get solutions from intelligent analysis, with fallbacks
            ai_actions = intelligent_analysis.get("developer_actions", [])
            
            if ai_actions:
                solution = ai_actions[:5]
            elif immediate_actions:
                solution = immediate_actions[:5]
            else:
                # Generate default solutions based on root cause
                solution = immediate_actions[:5]
                #solution = self._generate_default_solutions(root_cause, root_causes)
            
            summary = f"AI Analysis: {problem_identified}"
        else:
            # Fallback to basic analysis
            if not unhealthy_pods and not root_causes:
                problem_identified = "All pods are healthy"
                root_cause = "No issues detected"
                solution = ["Continue monitoring", "No immediate action required"]
                summary = "Kubernetes cluster is healthy with no pod issues"
            else:
                if not unhealthy_pods and root_causes:
                    problem_identified = f"Namespace '{namespace}' has configuration or resource issues"
                else:
                    problem_identified = f"Found {len(unhealthy_pods)} unhealthy pods in namespace '{namespace}'"
                
                root_cause = "; ".join(root_causes) if root_causes else "Pod health issues detected"
                
                # Enhanced solution generation based on root cause patterns
                if immediate_actions:
                    solution = immediate_actions[:5]
                else:
                    # Generate default solutions based on root cause
                    solution = self._generate_default_solutions(root_cause, root_causes)
                summary = f"Kubernetes namespace '{namespace}' has issues requiring attention: {root_cause}"
        
        # Get RAG solution based on problem and root cause
        rag_solution = await self._get_rag_solution(problem_identified, root_cause, "")
        
        # Get confidence information - we need to get the user prompt from somewhere
        # For now, we'll use a generic approach since we don't have direct access to user_prompt here
        user_prompt = f"kubernetes namespace {namespace}"  # This is a fallback
        confidence_info = ConfidenceDetector.detect_confidence(user_prompt)
        
        # Determine status based on findings
        status = "issues_found" if (unhealthy_pods or root_causes) else "success"
        
        # Return standardized format fields with RAG solution
        return {
            "status": status,
            "problem_identified": problem_identified,
            "root_cause": root_cause,
            "solution": solution,
            "summary": summary,
            "rag_solution": rag_solution,
            "confidence": confidence_info["confidence"],
            "confidence_level": confidence_info["confidence_level"],
            "confidence_reasoning": confidence_info["reasoning"],
            "intelligent_analysis": intelligent_analysis,  # Preserve for summarizer
            "unhealthy_pods": unhealthy_pods,               # Return the actual list
            "healthy_pods": findings.get("healthy_pods", []),  # Return the actual list  
            "events": findings.get("events", []),           # Return the actual list            "namespace": namespace,                         # For display
            "environment": findings.get("environment", "unknown")  # For display

        }
    
    async def _get_rag_solution(self, problem_identified: str, root_cause: str, user_query: str) -> Dict[str, Any]:
        """Get RAG solution based on problem and root cause analysis"""
        if not self.rag_service:
            return {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "RAG service not available"
            }
        
        try:
            # Get intelligent RAG solution
            rag_result = await self.rag_service.get_intelligent_rag_solution(
                problem_identified, 
                root_cause, 
                user_query
            )
            
            return rag_result
            
        except Exception as e:
            print(f"❌ RAG solution error: {str(e)}")
            return {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": f"RAG error: {str(e)}"
            }
    '''
    def _generate_default_solutions(self, root_cause: str, root_causes: list) -> list:
        """Generate default solutions based on root cause analysis"""
        solutions = []
        root_cause_lower = root_cause.lower()
        
        # Check for ImagePullBackOff/ErrImagePull issues
        if "image pull" in root_cause_lower or "imagepullbackoff" in root_cause_lower or "errimagepull" in root_cause_lower:
            solutions.extend([
                "Verify the container image exists in the registry",
                "Check image pull secrets and registry credentials", 
                "Validate the image tag is correct and available",
                "Ensure the registry URL is accessible from the cluster",
                "Check if the image name and tag are spelled correctly"
            ])
        
        # Check for container configuration errors
        elif "createcontainerconfigerror" in root_cause_lower or "config" in root_cause_lower:
            solutions.extend([
                "Check if all referenced secrets exist in the namespace",
                "Verify all configmaps are created and available",
                "Review environment variable configurations",
                "Validate volume mount configurations"
            ])
        
        # Check for crash loop issues
        elif "crashloopbackoff" in root_cause_lower or "restart loop" in root_cause_lower:
            solutions.extend([
                "Check container logs for application errors",
                "Review resource limits and requests",
                "Validate application startup configuration",
                "Check for missing dependencies or configuration"
            ])
        
        # Check for health probe failures
        elif "probe" in root_cause_lower or "health" in root_cause_lower:
            solutions.extend([
                "Review readiness and liveness probe configuration",
                "Check if the application is starting correctly",
                "Validate probe endpoints and timeouts",
                "Ensure the application is listening on the correct port"
            ])
        
        # Generic solutions if no specific pattern matched
        if not solutions:
            solutions.extend([
                "Check pod events for detailed error messages",
                "Review pod logs for application-specific errors",
                "Verify resource quotas and limits",
                "Check namespace configuration and permissions"
            ])
        
        return solutions[:5]  # Return max 5 solutions
    '''

