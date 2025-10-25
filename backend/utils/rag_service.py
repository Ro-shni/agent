#!/usr/bin/env python3
"""
RAG (Retrieval-Augmented Generation) service for historical solutions
Based on the implementation from up.py and utils.py
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed")
    
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
    
    async def get_intelligent_rag_solution(self, problem_identified: str, root_cause: str, user_query: str = "", context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get intelligent RAG solution based on problem_identified and root_cause analysis"""
        if not self.rag_available:
            return {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "RAG dependencies not available"
            }
            
        if not self.initialized:
            return {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "RAG service not initialized"
            }
        
        try:
            # Create enhanced query focusing on problem and root cause
            enhanced_query = self._create_problem_focused_query(problem_identified, root_cause, user_query)
            
            # Find similar incidents with higher threshold for better matches
            similar_incidents = await self.find_similar_incidents(enhanced_query, top_k=3, similarity_threshold=0.4)
            
            if not similar_incidents:
                return {
                    "rag_solution": None,
                    "similarity_score": 0.0,
                    "jira_id": None,
                    "message": "No similar historical incidents found for this problem"
                }
            
            # Get the best match (highest similarity score)
            best_match = similar_incidents[0]
            similarity_score = best_match.get("similarity_score", 0.0)
            jira_id = best_match.get("jira_id", "Unknown")
            
            # Extract the most relevant solution
            rag_solution = best_match.get("solution", "")
            if not rag_solution:
                # Fallback to summary if no solution
                rag_solution = best_match.get("summary", "No specific solution available")
            
            # Format the RAG solution with context
            formatted_solution = self._format_rag_solution(rag_solution, best_match, similarity_score)
            
            return {
                "rag_solution": formatted_solution,
                "similarity_score": round(similarity_score * 100, 2),  # Convert to percentage
                "jira_id": jira_id,
                "message": f"Found relevant solution from JIRA {jira_id} (Similarity: {similarity_score:.1%})"
            }
            
        except Exception as e:
            print(f"❌ Error getting intelligent RAG solution: {str(e)}")
            return {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": f"Error retrieving RAG solution: {str(e)}"
            }
    
    def _create_problem_focused_query(self, problem_identified: str, root_cause: str, user_query: str = "") -> str:
        """Create a focused query based on problem and root cause analysis"""
        # Combine problem, root cause, and user query for better matching
        query_parts = []
        
        if problem_identified and problem_identified.strip():
            query_parts.append(f"Problem: {problem_identified.strip()}")
        
        if root_cause and root_cause.strip():
            query_parts.append(f"Root cause: {root_cause.strip()}")
        
        if user_query and user_query.strip():
            query_parts.append(f"Context: {user_query.strip()}")
        
        # Join with spaces for better semantic matching
        enhanced_query = " ".join(query_parts)
        
        print(f"🔍 RAG Query: {enhanced_query}")
        return enhanced_query
    
    def _format_rag_solution(self, solution: str, incident: Dict[str, Any], similarity_score: float) -> str:
        """Format the RAG solution with additional context"""
        # Extract additional context from the incident
        jira_id = incident.get("jira_id", "Unknown")
        summary = incident.get("summary", "")
        severity = incident.get("severity", "")
        tags = incident.get("tags", [])
        
        # Format the solution with context
        formatted_solution = f"Based on similar incident {jira_id}:\n\n{solution}"
        
        # Add additional context if available
        if summary and summary != solution:
            formatted_solution += f"\n\nIncident Summary: {summary}"
        
        if severity:
            formatted_solution += f"\n\nSeverity: {severity}"
        
        if tags:
            formatted_solution += f"\n\nTags: {', '.join(tags)}"
        
        return formatted_solution
    
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


# Create global instance
rag_service = MongoDBRAGService(
    mongo_uri=os.getenv("MONGO_URI", "localhost:27017"),
    database="dev-ops-buddy",
    collection="JiraIssues"
)