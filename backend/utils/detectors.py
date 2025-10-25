"""
Utility classes for detecting context from user input or resource specifications.
"""
import re
from typing import Dict, Any, Optional, List
from .cluster_manager import SmartClusterManager
from .sql_service import mysql_service

class SmartContainerDetector:
    """Smart container detection for multi-container pods"""
    
    @staticmethod
    def detect_main_container(pod_data: Dict[str, Any], app_name: str) -> str:
        """Detect the main application container in a pod"""
        
        # Get container statuses from pod
        container_statuses = pod_data.get("status", {}).get("containerStatuses", [])
        container_specs = pod_data.get("spec", {}).get("containers", [])
        
        # Strategy 1: Container name matches app name
        for container in container_specs:
            container_name = container.get("name", "")
            if app_name in container_name or container_name in app_name:
                return container_name
        
        # Strategy 2: Look for non-sidecar containers (avoid common sidecar names)
        sidecar_patterns = [
            "telegraf", "fluentd", "fluent-bit", "jaeger", "istio", "envoy", 
            "prometheus", "grafana", "datadog", "newrelic", "sidecar", 
            "init", "proxy", "mesh", "linkerd"
        ]
        
        for container in container_specs:
            container_name = container.get("name", "").lower()
            is_sidecar = any(pattern in container_name for pattern in sidecar_patterns)
            if not is_sidecar:
                return container.get("name", "")
        
        # Strategy 3: Return the first container (usually main app)
        if container_specs:
            return container_specs[0].get("name", "")
        
        # Fallback: extract from pod name
        pod_name = pod_data.get("metadata", {}).get("name", "")
        if pod_name:
            # Remove deployment hash and replica parts
            base_name = re.sub(r'-[a-z0-9]{8,10}-[a-z0-9]{5}$', '', pod_name)
            base_name = re.sub(r'-[0-9]+$', '', base_name)
            return base_name
        
        return "unknown"


class DevOpsNamespaceDetector:
    """Enhanced namespace detection with MySQL integration"""
    
    def __init__(self):
        self.bu_mapping_cache = {}
        self.cache_ttl = 300  # 5 minutes cache
        self.last_cache_update = 0
    
    async def extract_namespace_info_from_user_input(self, user_input: str) -> Dict[str, Any]:
        """Extract namespace information from user input with MySQL integration"""
        result = {
            "environment": None,
            "business_unit": None,
            "applications": [],
            "namespaces": [],
            "cluster_context_needed": None,
            "issue_type": "unknown",
            "severity": "medium"
        }

        user_lower = user_input.lower()
        print(f"🔍 Analyzing user input: {user_input}")

        # -------- Issue Type Detection --------
        if any(word in user_lower for word in ["argocd", "argo", "deployment", "deploy", "rollout", "release"]):
            result["issue_type"] = "deployment"
            result["severity"] = "high"
        elif any(word in user_lower for word in ["crash", "crashloop", "backoff", "restart"]):
            result["issue_type"] = "crashloop"
            result["severity"] = "high"
        elif any(word in user_lower for word in ["health", "degraded", "unhealthy", "probe"]):
            result["issue_type"] = "health_check"
            result["severity"] = "high"
        elif any(word in user_lower for word in ["slow", "performance", "timeout"]):
            result["issue_type"] = "performance"
            result["severity"] = "medium"
        elif any(word in user_lower for word in ["error", "fail", "down"]):
            result["issue_type"] = "failure"
            result["severity"] = "high"
        else:
            result["issue_type"] = "unknown"
            result["severity"] = "medium"

        # -------- Environment Detection --------
        env_patterns = [
            (r'\bstg\b|\bstaging\b', 'stg'),
            (r'\bprd\b|\bprod\b|\bproduction\b', 'prd'),
            (r'\bint\b|\bintegration\b', 'int'),
            (r'\bdev\b', 'dev')
        ]
        for pattern, env in env_patterns:
            if re.search(pattern, user_lower):
                result["environment"] = env
                print(f"   🎯 Detected environment: {env}")
                break

        # -------- Business Unit Detection --------
        bu_patterns = [
            (r'\bsupply\s+(stg|prd|int|dev)\b', 'supply'),
            (r'\bcentral\s+(stg|prd|int|dev)\b', 'central'),
            (r'\bdemand\s+(stg|prd|int|dev)\b', 'demand'),
            (r'\badmin\s+(stg|prd|int|dev)\b', 'admin'),
            (r'\bdataengg\s+(stg|prd|dev)\b', 'dataengg'),
            (r'\bdatascience\s+(prd|dev)\b', 'datascience'),
            # Add patterns for "in central cluster", "central stg cluster" etc
            (r'\bin\s+central\s+(cluster|stg|prd|int|dev)', 'central'),
            (r'\bin\s+supply\s+(cluster|stg|prd|int|dev)', 'supply'),
            (r'\bin\s+demand\s+(cluster|stg|prd|int|dev)', 'demand'),
            (r'\bin\s+admin\s+(cluster|stg|prd|int|dev)', 'admin'),
            # Pattern for "central stg cluster"
            (r'\bcentral\s+stg\s+cluster\b', 'central'),
            (r'\bsupply\s+stg\s+cluster\b', 'supply'),
            (r'\bdemand\s+stg\s+cluster\b', 'demand'),
            (r'\bsupply[-\s]+(stg|prd|int|dev)\b', 'supply'),
            (r'\bcentral[-\s]+(stg|prd|int|dev)\b', 'central'),
            (r'\bdemand[-\s]+(stg|prd|int|dev)\b', 'demand'),
            (r'\badmin[-\s]+(stg|prd|int|dev)\b', 'admin'),
            (r'\bdataengg[-\s]+(stg|prd|dev)\b', 'dataengg'),
            (r'\bdatascience[-\s]+(prd|dev)\b', 'datascience'),
        ]
        
        for pattern, bu in bu_patterns:
            if re.search(pattern, user_lower):
                result["business_unit"] = bu
                print(f"   🏢 Detected business unit: {bu}")
                break

        # -------- Namespace & Application Extraction --------
        # Pattern: env-appname
        namespace_pattern = r'\b(stg|prd|int|dev)-([a-z0-9][a-z0-9\-]*[a-z0-9]|[a-z0-9]+)\b'
        namespace_matches = re.findall(namespace_pattern, user_lower)
        print(f"   🔍 Found namespace matches: {namespace_matches}")

        seen_apps = set()
        for env, app in namespace_matches:
            namespace = f"{env}-{app}"
            if app not in seen_apps:
                result["applications"].append(app)
                seen_apps.add(app)
                print(f"   📱 Added application: {app}")
            if namespace not in result["namespaces"]:
                result["namespaces"].append(namespace)
                print(f"   🏷️ Added namespace: {namespace}")

            # -------- Business Unit from MySQL Mapping --------
            bu = await self._get_business_unit_for_app(app)
            if bu and not result["business_unit"]:
                result["business_unit"] = bu
                print(f"   🏢 Mapped to business unit: {bu}")

        # -------- Pattern for "APP in BUSINESS_UNIT ENV" format --------
        crash_pattern = r'(?:for|in)\s+([a-z0-9][a-z0-9\-]*[a-z0-9]|[a-z0-9]+)\s+(?:which\s+is\s+)?in\s+(\w+)\s+(stg|prd|int|dev)'
        crash_match = re.search(crash_pattern, user_lower)
        if crash_match:
            app_name = crash_match.group(1)
            bu = crash_match.group(2)
            env = crash_match.group(3)
            print(f"   🔍 Found pattern match: app={app_name}, bu={bu}, env={env}")

            if not app_name.startswith(f"{env}-") and app_name not in result["applications"]:
                result["applications"].append(app_name)
                print(f"   📱 Added application from pattern: {app_name}")
            if not result["business_unit"]:
                result["business_unit"] = bu
                print(f"   🏢 Set business unit from pattern: {bu}")
            if not result["environment"]:
                result["environment"] = env
                print(f"   🎯 Set environment from pattern: {env}")

            namespace = f"{env}-{app_name}"
            if namespace not in result["namespaces"]:
                result["namespaces"].append(namespace)
                print(f"   🏷️ Added namespace from pattern: {namespace}")

        if "argocd" in user_lower and "meeshogcp.in" in user_lower:
            print(f"   🔍 Detecting ArgoCD URL")
            argocd_pattern = r'argocd-(\w+)\.meeshogcp\.in/applications/argocd-\1/(.+?)(?:\?|$)'
            
            argocd_match = re.search(argocd_pattern, user_lower)
            if argocd_match:
                argocd_env = argocd_match.group(1)  # 'dev' from domain
                full_app_name = argocd_match.group(2)  # 'stg-aggregation-platform-consumer'
                
                print(f"   🎯 Detected ArgoCD URL: argocd_env={argocd_env}, full_app_name={full_app_name}")
                
                # Extract actual environment and app name from the full application name
                app_parts = full_app_name.split('-', 1)
                if len(app_parts) >= 2:
                    actual_env = app_parts[0]  # 'stg'
                    app_name = app_parts[1]    # 'aggregation-platform-consumer'
                    
                    # Set environment (use the actual app environment, not ArgoCD instance env)
                    result["environment"] = actual_env
                    print(f"   🎯 Detected environment from ArgoCD: {actual_env}")
                    
                    # Add application
                    if app_name not in result["applications"]:
                        result["applications"].append(app_name)
                        print(f"   📱 Added application from ArgoCD: {app_name}")
                    
                    # Create namespace
                    namespace = f"{actual_env}-{app_name}"
                    if namespace not in result["namespaces"]:
                        result["namespaces"].append(namespace)
                        print(f"   🏷️ Added namespace from ArgoCD: {namespace}")
                    
                    # Get business unit for the app
                    print(f"   🔍 Looking up business unit for ArgoCD app: {app_name}")
                    bu = await self._get_business_unit_for_app(app_name)
                    print(f"   🔍 ArgoCD business unit lookup result: {bu}")
                    if bu:
                        if not result["business_unit"]:
                            result["business_unit"] = bu
                            print(f"   🏢 Mapped ArgoCD app to business unit: {bu}")
                        else:
                            print(f"   ✅ Business unit already set to: {result['business_unit']}, ArgoCD app also maps to: {bu}")
                    else:
                        print(f"   ⚠️ No business unit found for ArgoCD app: {app_name}")                        # Try alternative app name patterns
                        alternative_names = [
                            app_name.replace('-', ''),
                            app_name.replace('_', ''),
                            app_name.split('-')[0],  # First part before any dashes
                            app_name.split('_')[0]   # First part before any underscores
                        ]
                        for alt_name in alternative_names:
                            if alt_name != app_name:
                                print(f"   🔍 Trying alternative app name: {alt_name}")
                                bu = await self._get_business_unit_for_app(alt_name)
                                if bu:
                                    result["business_unit"] = bu
                                    print(f"   🏢 Mapped alternative app name to business unit: {bu}")
                                    break
                        
                        # If still no business unit found, try fuzzy matching in MySQL
                        if not result["business_unit"]:
                            print(f"   🔍 Trying fuzzy matching for app '{app_name}' in MySQL")
                            fuzzy_bu = await self._get_business_unit_fuzzy_match(app_name)
                            if fuzzy_bu:
                                result["business_unit"] = fuzzy_bu
                                print(f"   🏢 Mapped app '{app_name}' to business unit '{fuzzy_bu}' using fuzzy matching")
                            else:
                                print(f"   ⚠️ No business unit found for app '{app_name}' even with fuzzy matching")                    
                    result["issue_type"] = "deployment"
                    result["severity"] = "high"  # ArgoCD issues are typically high severity
                    print(f"   🎯 Set ArgoCD issue type: deployment, severity: high")
                    
                else:
                    # Handle case where app name doesn't follow env-appname pattern
                    print(f"   ⚠️ ArgoCD app name doesn't follow env-appname pattern: {full_app_name}")
                    result["environment"] = argocd_env  # Fallback to ArgoCD instance env
                    result["applications"].append(full_app_name)
                    result["namespaces"].append(f"{argocd_env}-{full_app_name}")
                
                # Don't return here - continue to cluster context detection       


        if "github.com" in user_lower:

            github_pattern = r'github\.com/[^/]+/([^/]+)'
            github_match = re.search(github_pattern, user_lower)
            if github_match:
                repo_name = github_match.group(1)

                app_name = re.sub(r'(-bot|-service|-web|-api)$', '', repo_name).lower()
                print(f"   🔍 Converted repo name '{repo_name}' to app name '{app_name}'")
                if app_name and app_name not in result["applications"]:
                    result["applications"].append(app_name)
                    print(f"   📱 Added application from GitHub repo: {app_name}")
                    
                    # Try to detect environment from bot comments or user input
                    if not result["environment"]:
                        # Check for environment keywords in the user input
                        if "int" in user_lower or "integration" in user_lower:
                            result["environment"] = "int"
                            print(f"   🎯 Detected int environment from user input")
                        elif "stg" in user_lower or "staging" in user_lower:
                            result["environment"] = "stg"
                            print(f"   🎯 Detected stg environment from user input")
                        elif "prd" in user_lower or "prod" in user_lower or "production" in user_lower:
                            result["environment"] = "prd"
                            print(f"   🎯 Detected prd environment from user input")
                        else:
                            # No environment detected - leave as None
                            print(f"   ⚠️ No environment detected for GitHub PR")
                    
                    # Override environment if we detect "int" in the user input (from bot comments)
                    if "int" in user_lower and result["environment"] != "int":
                        result["environment"] = "int"
                        print(f"   🎯 Overriding environment to int based on bot comments")
                    
                    # Update namespace with the correct environment
                    if result["environment"] != "stg":
                        # Remove old namespace and add new one
                        old_namespace = f"stg-{app_name}"
                        if old_namespace in result["namespaces"]:
                            result["namespaces"].remove(old_namespace)
                        new_namespace = f"{result['environment']}-{app_name}"
                        if new_namespace not in result["namespaces"]:
                            result["namespaces"].append(new_namespace)
                            print(f"   🏷️ Updated namespace to: {new_namespace}")
                    
                    # Create namespace (if not already added above)
                    namespace = f"{result['environment']}-{app_name}"
                    if namespace not in result["namespaces"]:
                        result["namespaces"].append(namespace)
                        print(f"   🏷️ Added namespace from GitHub repo: {namespace}")
                    
                    # Get business unit for the app
                    print(f"   🔍 Looking up business unit for app: {app_name}")
                    bu = await self._get_business_unit_for_app(app_name)
                    print(f"   🔍 Business unit lookup result: {bu}")
                    if bu and not result["business_unit"]:
                        result["business_unit"] = bu
                        print(f"   🏢 Mapped to business unit: {bu}")
                    else:
                        print(f"   ⚠️ No business unit found for app: {app_name}")
                        # Try alternative app names
                        alternative_names = [
                            app_name.replace("service", ""),
                            app_name.replace("service", "-service"),
                            f"{app_name}-service",
                            app_name.replace("-", ""),
                            app_name.replace("-", "_")
                        ]
                        for alt_name in alternative_names:
                            if alt_name != app_name:
                                print(f"   🔍 Trying alternative app name: {alt_name}")
                                alt_bu = await self._get_business_unit_for_app(alt_name)
                                if alt_bu:
                                    result["business_unit"] = alt_bu
                                    print(f"   🏢 Mapped to business unit using alternative name: {alt_bu}")
                                    break
                    
                    # Set issue type and severity based on context
                    if "health" in user_lower or result["issue_type"] == "health_check":
                        result["issue_type"] = "health_check"
                        result["severity"] = "high"
                        print(f"   🔍 Set issue type: {result['issue_type']}, severity: {result['severity']}")
                    else:
                        result["issue_type"] = "github_pr_analysis"
                        result["severity"] = "medium"
                        print(f"   🔍 Set issue type: {result['issue_type']}, severity: {result['severity']}")

        print(f"   🔍 Cluster context detection: bu={result['business_unit']}, env={result['environment']}")
        if result["business_unit"] and result["environment"]:
            print(f"   🔍 Finding cluster context for bu={result['business_unit']}, env={result['environment']}")
            result["cluster_context_needed"] = await self._find_matching_context(
                result["business_unit"],
                result["environment"]
            )
            print(f"   🎯 Cluster context needed: {result['cluster_context_needed']}")
        else:
            print(f"   ⚠️ Skipping cluster context detection - missing bu or env")

        print(f"   📊 Final result: {result}")
        return result
    
    async def _get_business_unit_for_app(self, app_name: str) -> Optional[str]:

        """Get business unit for application from MySQL"""
        try:
            return await mysql_service.get_business_unit_for_app(app_name)
        except Exception as e:
            print(f"⚠️ Failed to get BU for {app_name}: {str(e)}")
            return None

    async def _get_business_unit_fuzzy_match(self, app_name: str) -> Optional[str]:
        """Get business unit using fuzzy matching for similar app names"""
        try:
            return await mysql_service.get_business_unit_fuzzy_match(app_name)
        except Exception as e:
            print(f"⚠️ Failed to fuzzy match BU for {app_name}: {str(e)}")
            return None
    
    async def _find_matching_context(self, business_unit: str, environment: str) -> Optional[str]:
        """Find matching Kubernetes context based on business unit and environment"""
        try:
            print(f"   🔍 Finding cluster context for bu='{business_unit}', env='{environment}'")
            
            # Use the SmartClusterManager to find the matching context
            from .cluster_manager import SmartClusterManager
            matching_context = SmartClusterManager.find_matching_context(business_unit, environment)
            
            if matching_context:
                print(f"   ✅ Found matching context: {matching_context}")
                return matching_context
            else:
                print(f"   ⚠️ No matching context found for bu='{business_unit}', env='{environment}'")
                return None
            
        except Exception as e:
            print(f"⚠️ Failed to find matching context: {str(e)}")
            return None
    
    async def get_service_mapping(self) -> Dict[str, str]:
        """Get the complete service to business unit mapping"""
        try:
            return await mysql_service.get_service_details()
        except Exception as e:
            print(f"⚠️ Failed to get service mapping: {str(e)}")
            return {}
    
    async def search_services(self, pattern: str) -> List[Dict[str, Any]]:
        """Search services by pattern"""
        try:
            return await mysql_service.search_services_by_pattern(pattern)
        except Exception as e:
            print(f"⚠️ Failed to search services: {str(e)}")
            return []

class Detector:
    """Detect URL type from user prompt for intelligent routing"""
    @staticmethod
    def detect_url_type(user_prompt: str) -> str:
        """Detect URL type from user prompt for intelligent routing"""
        import re
        
        # ArgoCD URL patterns
        argocd_patterns = [
            r'https://argocd-.*\.meeshogcp\.in/',
            r'argocd.*meeshogcp\.in',
            r'argocd.*application',
            r'argocd.*applications'
        ]
        
        # Jenkins URL patterns  
        jenkins_patterns = [
            r'https://jenkins-.*\.meeshogcp\.in/',
            r'jenkins.*meeshogcp\.in',
            r'jenkins.*console',
            r'jenkins.*build',
            r'jenkins.*job'
        ]
        
        # GitHub URL patterns
        github_patterns = [
            r'github\.com/.*pull/',
            r'github\.com/.*issues/',
            r'github\.com/.*actions/',
            r'pull.*request',
            r'pr.*#\d+'
        ]
        
        # Kubernetes URL patterns
        k8s_patterns = [
            r'kubernetes.*namespace',
            r'k8s.*pod',
            r'cluster.*debug',
            r'deployment.*status'
        ]
        
        # Check patterns in order of specificity
        for pattern in argocd_patterns:
            if re.search(pattern, user_prompt, re.IGNORECASE):
                return "kubernetes"  # ArgoCD URLs should route to K8s agent
                
        for pattern in jenkins_patterns:
            if re.search(pattern, user_prompt, re.IGNORECASE):
                return "jenkins"
                
        for pattern in github_patterns:
            if re.search(pattern, user_prompt, re.IGNORECASE):
                return "github"
                
        for pattern in k8s_patterns:
            if re.search(pattern, user_prompt, re.IGNORECASE):
                return "kubernetes"
        
        return "general"  # Default fallback


# Global instance
namespace_detector = DevOpsNamespaceDetector()
