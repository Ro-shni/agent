"""
Utility classes and functions for the DevOps orchestrator
"""

import json
import yaml
import subprocess
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

# Optional imports for RAG functionality
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ RAG dependencies not available: {e}")
    print("⚠️ RAG functionality will be disabled")
    RAG_AVAILABLE = False

class ToolCallLogger:
    """Real-time tool call streaming logger"""
    
    @staticmethod
    def log_tool_call(tool_name: str, parameters: Dict[str, Any], step: int):
        """Log tool call in real-time"""
        print(f"\n🔧 TOOL CALL #{step}: {tool_name}")
        print(f"📋 Parameters: {json.dumps(parameters, indent=2)}")
        print(f"⏳ Executing...")
    
    @staticmethod
    def log_tool_result(tool_name: str, result_summary: str, step: int):
        """Log tool result"""
        print(f"✅ Result: {result_summary}")
        print(f"⏱️ Tool call #{step} completed")
    
    @staticmethod
    def log_analysis_step(step_name: str, description: str):
        """Log analysis step"""
        print(f"\n🔍 DEVOPS STEP: {step_name}")
        print(f"📝 {description}")


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
            import re
            base_name = re.sub(r'-[a-z0-9]{8,10}-[a-z0-9]{5}$', '', pod_name)
            base_name = re.sub(r'-[0-9]+$', '', base_name)
            return base_name
        
        return "unknown"


class SmartClusterManager:
    """Smart cluster context management with business unit detection"""
    
    @staticmethod
    def get_available_contexts() -> Dict[str, Any]:
        """Get available kubectl contexts"""
        try:
            result = subprocess.run(
                ['kubectl', 'config', 'get-contexts', '-o', 'name'], 
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                contexts = [ctx.strip() for ctx in result.stdout.split('\n') if ctx.strip()]
                return {"contexts": contexts, "error": None}
            else:
                return {"contexts": [], "error": f"kubectl failed: {result.stderr}"}
        except Exception as e:
            return {"contexts": [], "error": f"Failed to get contexts: {str(e)}"}
    
    @staticmethod
    def get_current_context() -> Dict[str, Any]:
        """Get current kubectl context"""
        try:
            result = subprocess.run(
                ['kubectl', 'config', 'current-context'], 
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return {"current_context": result.stdout.strip(), "error": None}
            else:
                return {"current_context": None, "error": f"kubectl failed: {result.stderr}"}
        except Exception as e:
            return {"current_context": None, "error": f"Failed to get current context: {str(e)}"}
    
    @staticmethod
    def switch_context(context_name: str) -> Dict[str, Any]:
        """Switch kubectl context"""
        try:
            result = subprocess.run(
                ['kubectl', 'config', 'use-context', context_name], 
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return {"success": True, "message": f"Switched to context: {context_name}"}
            else:
                return {"success": False, "error": f"Failed to switch: {result.stderr}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to switch: {str(e)}"}
    
    @staticmethod
    def find_matching_context(business_unit: str, environment: str) -> Optional[str]:
        """Find matching context based on business unit and environment"""
        contexts_info = SmartClusterManager.get_available_contexts()
        if contexts_info["error"]:
            return None
        
        contexts = contexts_info["contexts"]
        if environment == "int":
            for context in contexts:
                if "shared-int" in context:
                    return context

        # Context pattern: gke_meesho-{bu}-{proj}-0622_asia-southeast1_k8s-{bu}-{env}-ase1
        # Project mapping: dev project for stg env, prd project for prd env
        project_mapping = {
            "stg": "dev",
            "prd": "prd", 
            "int": "int"
        }
        
        project = project_mapping.get(environment, "dev")
        
        # Try exact match first
        expected_pattern = f"gke_meesho-{business_unit}-{project}-0622_asia-southeast1_k8s-{business_unit}-{environment}-ase1"
        
        for context in contexts:
            if context == expected_pattern:
                return context
        
        # Try fuzzy match
        for context in contexts:
            if business_unit in context and environment in context:
                return context
        
        return None


class DevOpsNamespaceDetector:
    """Smart namespace detection for DevOps scenarios"""
    
    @staticmethod
    def extract_namespace_info_from_user_input(user_input: str) -> Dict[str, Any]:
        """Extract namespace info from user input with DevOps context"""
        import re
        
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
        
        # Issue type detection
        if any(word in user_lower for word in ["crash", "crashloop", "backoff", "restart"]):
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
        
        # Environment detection
        env_patterns = [
            (r'\bstg\b|\bstaging\b', 'stg'),
            (r'\bprd\b|\bprod\b|\bproduction\b', 'prd'),
            (r'\bint\b|\bintegration\b', 'int')
        ]
        
        for pattern, env in env_patterns:
            if re.search(pattern, user_lower):
                result["environment"] = env
                break
        
        # Business unit detection
        bu_patterns = [
            (r'\bsupply\s+(stg|prd|int)\b', 'supply'),
            (r'\bcentral\s+(stg|prd|int)\b', 'central'),
            (r'\bdemand\s+(stg|prd|int)\b', 'demand'),
            (r'\badmin\s+(stg|prd|int)\b', 'admin'),
            (r'\bdataengg\s+(stg|prd)\b', 'dataengg'),
            (r'\bdatascience\s+prd\b', 'datascience'),
            # Add patterns for "in central cluster", "central stg cluster" etc
            (r'\bin\s+central\s+(cluster|stg|prd|int)', 'central'),
            (r'\bin\s+supply\s+(cluster|stg|prd|int)', 'supply'),
            (r'\bin\s+demand\s+(cluster|stg|prd|int)', 'demand'),
            (r'\bin\s+admin\s+(cluster|stg|prd|int)', 'admin'),
            # Pattern for "central stg cluster"
            (r'\bcentral\s+stg\s+cluster\b', 'central'),
            (r'\bsupply\s+stg\s+cluster\b', 'supply'),
            (r'\bdemand\s+stg\s+cluster\b', 'demand'),
            (r'\bsupply[-\s]+(stg|prd|int)\b', 'supply'),
            (r'\bcentral[-\s]+(stg|prd|int)\b', 'central'),
            (r'\bdemand[-\s]+(stg|prd|int)\b', 'demand'),
            (r'\badmin[-\s]+(stg|prd|int)\b', 'admin'),
            (r'\bdataengg[-\s]+(stg|prd)\b', 'dataengg'),
            (r'\bdatascience[-\s]+prd\b', 'datascience'),

        ]
        
        for pattern, bu in bu_patterns:
            if re.search(pattern, user_lower):
                result["business_unit"] = bu
                break
        
        # Application name detection
        namespace_pattern = r'\b(stg|prd|int)-([a-z0-9][a-z0-9\-]*[a-z0-9]|[a-z0-9])\b'
        namespace_matches = re.findall(namespace_pattern, user_lower)
        
        seen_apps = set()
        for env, app in namespace_matches:
            if env == result.get("environment") and app not in seen_apps:
                result["applications"].append(app)
                seen_apps.add(app)
                namespace = f"{env}-{app}"
                if namespace not in result["namespaces"]:
                    result["namespaces"].append(namespace)
        
        # Pattern for "APP in BUSINESS_UNIT ENV" format
        crash_pattern = r'(?:for|in)\s+([a-z0-9][a-z0-9\-]*[a-z0-9]|[a-z0-9])\s+(?:which\s+is\s+)?in\s+(\w+)\s+(stg|prd|int)'
        crash_match = re.search(crash_pattern, user_lower)
        if crash_match:
            app_name = crash_match.group(1)
            bu = crash_match.group(2)
            env = crash_match.group(3)
            
            # Avoid adding env prefix again if already there
            if not app_name.startswith(f"{env}-") and app_name not in result["applications"]:
                result["applications"].append(app_name)
            if not result["business_unit"]:
                result["business_unit"] = bu
            if not result["environment"]:
                result["environment"] = env
            
            namespace = f"{env}-{app_name}"
            if namespace not in result["namespaces"]:
                result["namespaces"].append(namespace)
        
        # Set cluster context needed
        if result["environment"] == "int":
            result["cluster_context_needed"] = SmartClusterManager.find_matching_context(
                result["business_unit"], 
                result["environment"]
            )

        if result["business_unit"] and result["environment"]:
            result["cluster_context_needed"] = SmartClusterManager.find_matching_context(
                result["business_unit"], 
                result["environment"]
            )
        
        return result


def parse_k8s_yaml_output(yaml_text: str) -> List[Dict[str, Any]]:
    """Parse Kubernetes YAML output"""
    if not yaml_text or not isinstance(yaml_text, str):
        return []
    
    try:
        if '---' in yaml_text:
            documents = yaml_text.split('---')
            resources = []
            for doc in documents:
                if doc.strip():
                    parsed = yaml.safe_load(doc.strip())
                    if parsed:
                        if isinstance(parsed, list):
                            resources.extend(parsed)
                        else:
                            resources.append(parsed)
            return resources
        else:
            resources = yaml.safe_load(yaml_text)
            if isinstance(resources, list):
                return resources
            elif isinstance(resources, dict):
                if resources.get('kind') == 'List' and 'items' in resources:
                    return resources['items']
                return [resources]
            else:
                return []
    except yaml.YAMLError:
        return []


class MongoDBRAGService:
    """MongoDB-based RAG service for historical incident solution retrieval"""
    
    def __init__(self, mongo_uri: str, database: str, collection: str, timeout: int = 30):
        self.mongo_uri = mongo_uri
        self.database_name = database
        self.collection_name = collection
        self.timeout = timeout
        self.client = None
        self.db = None
        self.collection = None
        self.embedding_model = None
        self.incident_embeddings = None
        self.incident_documents = None
        self.initialized = False
        self.rag_available = RAG_AVAILABLE
    
    async def initialize(self) -> bool:
        """Initialize MongoDB connection and load incident data"""
        if not self.rag_available:
            print("⚠️ RAG dependencies not available - skipping RAG initialization")
            return False
            
        try:
            print("🔄 Initializing MongoDB RAG Service...")
            
            # Initialize MongoDB connection
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=self.timeout * 1000)
            
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            self.collection = self.db[self.collection_name]
            
            print(f"✅ Connected to MongoDB: {self.database_name}.{self.collection_name}")
            
            # Initialize embedding model
            print("🔄 Loading sentence transformer model...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Load and embed incident data
            await self._load_incident_embeddings()
            
            self.initialized = True
            print("✅ MongoDB RAG Service initialized successfully!")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"❌ MongoDB connection failed: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ RAG Service initialization failed: {str(e)}")
            return False
    
    async def _load_incident_embeddings(self):
        """Load incident data and create embeddings"""
        try:
            print("🔄 Loading incident data from MongoDB...")
            
            # Fetch all incidents with incident_report
            incidents = list(self.collection.find({
                "incident_report": {"$exists": True},
                "incident_report.incident_description": {"$exists": True, "$ne": ""}
            }))
            
            if not incidents:
                print("⚠️ No incidents found in database")
                self.incident_embeddings = np.array([])
                self.incident_documents = []
                return
            
            print(f"📊 Found {len(incidents)} incidents with descriptions")
            
            # Extract incident descriptions and metadata
            incident_texts = []
            incident_metadata = []
            
            for incident in incidents:
                incident_desc = incident.get("incident_report", {}).get("incident_description", "")
                if incident_desc and incident_desc.strip():
                    # Create searchable text combining description, root cause, and solution
                    searchable_text = self._create_searchable_text(incident)
                    incident_texts.append(searchable_text)
                    incident_metadata.append({
                        "jira_id": incident.get("jira_id", "Unknown"),
                        "summary": incident.get("summary", ""),
                        "description": incident_desc,
                        "root_cause": incident.get("incident_report", {}).get("root_cause", ""),
                        "solution": incident.get("incident_report", {}).get("solution", ""),
                        "impacted_services": incident.get("incident_report", {}).get("impacted_services", []),
                        "tags": incident.get("incident_report", {}).get("tags", []),
                        "severity": incident.get("incident_report", {}).get("severity", ""),
                        "created_at": incident.get("created_at"),
                        "updated_at": incident.get("updated_at")
                    })
            
            if not incident_texts:
                print("⚠️ No valid incident descriptions found")
                self.incident_embeddings = np.array([])
                self.incident_documents = []
                return
            
            # Create embeddings
            print("🔄 Creating embeddings for incident descriptions...")
            self.incident_embeddings = self.embedding_model.encode(incident_texts)
            self.incident_documents = incident_metadata
            
            print(f"✅ Created embeddings for {len(incident_texts)} incidents")
            
        except Exception as e:
            print(f"❌ Failed to load incident embeddings: {str(e)}")
            self.incident_embeddings = np.array([])
            self.incident_documents = []
    
    def _create_searchable_text(self, incident: Dict[str, Any]) -> str:
        """Create searchable text from incident data"""
        parts = []
        
        # Add summary
        summary = incident.get("summary", "")
        if summary:
            parts.append(f"Summary: {summary}")
        
        # Add incident description
        incident_desc = incident.get("incident_report", {}).get("incident_description", "")
        if incident_desc:
            parts.append(f"Description: {incident_desc}")
        
        # Add root cause
        root_cause = incident.get("incident_report", {}).get("root_cause", "")
        if root_cause:
            parts.append(f"Root Cause: {root_cause}")
        
        # Add solution
        solution = incident.get("incident_report", {}).get("solution", "")
        if solution:
            parts.append(f"Solution: {solution}")
        
        # Add impacted services
        services = incident.get("incident_report", {}).get("impacted_services", [])
        if services:
            parts.append(f"Services: {', '.join(services)}")
        
        # Add tags
        tags = incident.get("incident_report", {}).get("tags", [])
        if tags:
            parts.append(f"Tags: {', '.join(tags)}")
        
        return " | ".join(parts)
    
    async def find_similar_incidents(self, query: str, top_k: int = 3, similarity_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """Find similar incidents based on query using semantic similarity"""
        if not self.initialized or len(self.incident_documents) == 0:
            return []
        
        try:
            # Create query embedding
            query_embedding = self.embedding_model.encode([query])
            
            # Calculate similarities
            similarities = cosine_similarity(query_embedding, self.incident_embeddings)[0]
            
            # Get top similar incidents
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            similar_incidents = []
            for idx in top_indices:
                similarity_score = similarities[idx]
                if similarity_score >= similarity_threshold:
                    incident = self.incident_documents[idx].copy()
                    incident["similarity_score"] = float(similarity_score)
                    similar_incidents.append(incident)
            
            return similar_incidents
            
        except Exception as e:
            print(f"❌ Error finding similar incidents: {str(e)}")
            return []
    
    async def get_historical_solutions(self, user_query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get historical solutions based on user query"""
        if not self.rag_available:
            return {
                "solutions_found": False,
                "message": "RAG dependencies not available",
                "historical_incidents": [],
                "recommended_solutions": []
            }
            
        if not self.initialized:
            return {
                "solutions_found": False,
                "message": "RAG service not initialized",
                "historical_incidents": [],
                "recommended_solutions": []
            }
        
        try:
            # Enhance query with context if available
            enhanced_query = self._enhance_query_with_context(user_query, context)
            
            # Find similar incidents
            similar_incidents = await self.find_similar_incidents(enhanced_query, top_k=5)
            
            if not similar_incidents:
                return {
                    "solutions_found": False,
                    "message": "No similar historical incidents found",
                    "historical_incidents": [],
                    "recommended_solutions": []
                }
            
            # Extract solutions and recommendations
            solutions = []
            for incident in similar_incidents:
                if incident.get("solution") and incident["solution"].strip():
                    solutions.append({
                        "jira_id": incident.get("jira_id", "Unknown"),
                        "summary": incident.get("summary", ""),
                        "solution": incident["solution"],
                        "root_cause": incident.get("root_cause", ""),
                        "impacted_services": incident.get("impacted_services", []),
                        "tags": incident.get("tags", []),
                        "severity": incident.get("severity", ""),
                        "similarity_score": incident.get("similarity_score", 0.0),
                        "created_at": incident.get("created_at"),
                        "updated_at": incident.get("updated_at")
                    })
            
            # Generate recommendations based on historical data
            recommendations = self._generate_recommendations(similar_incidents, user_query)
            
            return {
                "solutions_found": len(solutions) > 0,
                "message": f"Found {len(solutions)} historical solutions",
                "historical_incidents": similar_incidents,
                "recommended_solutions": solutions,
                "recommendations": recommendations
            }
            
        except Exception as e:
            print(f"❌ Error getting historical solutions: {str(e)}")
            return {
                "solutions_found": False,
                "message": f"Error retrieving solutions: {str(e)}",
                "historical_incidents": [],
                "recommended_solutions": []
            }
    
    def _enhance_query_with_context(self, user_query: str, context: Dict[str, Any] = None) -> str:
        """Enhance user query with additional context"""
        if not context:
            return user_query
        
        enhanced_parts = [user_query]
        
        # Add namespace/environment context
        if context.get("namespace"):
            enhanced_parts.append(f"namespace: {context['namespace']}")
        
        if context.get("environment"):
            enhanced_parts.append(f"environment: {context['environment']}")
        
        # Add service context
        if context.get("services"):
            services = context["services"]
            if isinstance(services, list):
                enhanced_parts.append(f"services: {', '.join(services)}")
            else:
                enhanced_parts.append(f"service: {services}")
        
        # Add issue type context
        if context.get("issue_type"):
            enhanced_parts.append(f"issue type: {context['issue_type']}")
        
        # Add error patterns
        if context.get("error_patterns"):
            patterns = context["error_patterns"]
            if isinstance(patterns, list):
                enhanced_parts.append(f"error patterns: {', '.join(patterns)}")
            else:
                enhanced_parts.append(f"error: {patterns}")
        
        return " | ".join(enhanced_parts)
    
    def _generate_recommendations(self, similar_incidents: List[Dict[str, Any]], user_query: str) -> List[str]:
        """Generate recommendations based on similar incidents"""
        recommendations = []
        
        # Extract common patterns from similar incidents
        common_tags = {}
        common_services = {}
        common_solutions = {}
        
        for incident in similar_incidents:
            # Count tags
            for tag in incident.get("tags", []):
                common_tags[tag] = common_tags.get(tag, 0) + 1
            
            # Count services
            for service in incident.get("impacted_services", []):
                common_services[service] = common_services.get(service, 0) + 1
            
            # Extract solution keywords
            solution = incident.get("solution", "").lower()
            if solution:
                # Simple keyword extraction
                keywords = re.findall(r'\b\w+\b', solution)
                for keyword in keywords:
                    if len(keyword) > 3:  # Filter short words
                        common_solutions[keyword] = common_solutions.get(keyword, 0) + 1
        
        # Generate recommendations based on patterns
        if common_tags:
            top_tags = sorted(common_tags.items(), key=lambda x: x[1], reverse=True)[:3]
            recommendations.append(f"Common issue categories: {', '.join([tag for tag, _ in top_tags])}")
        
        if common_services:
            top_services = sorted(common_services.items(), key=lambda x: x[1], reverse=True)[:3]
            recommendations.append(f"Frequently affected services: {', '.join([service for service, _ in top_services])}")
        
        # Add specific recommendations based on query content
        query_lower = user_query.lower()
        
        if any(word in query_lower for word in ["config", "configuration", "configmap", "secret"]):
            recommendations.append("Check configuration files and environment variables")
        
        if any(word in query_lower for word in ["deploy", "deployment", "rollout"]):
            recommendations.append("Review deployment strategy and rollback procedures")
        
        if any(word in query_lower for word in ["health", "probe", "readiness", "liveness"]):
            recommendations.append("Verify health check configurations and application startup")
        
        if any(word in query_lower for word in ["memory", "oom", "resource"]):
            recommendations.append("Check resource limits and memory usage patterns")
        
        if any(word in query_lower for word in ["network", "connection", "timeout"]):
            recommendations.append("Investigate network connectivity and timeout settings")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed")
