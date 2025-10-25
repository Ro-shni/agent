"""
Confidence detection module for DevOps analysis queries.
Determines if a query is suitable for automated analysis and provides confidence levels.
"""
import re
from typing import Dict, Any, List, Tuple
from .detectors import Detector

class ConfidenceDetector:
    """Detects confidence levels for DevOps analysis queries"""
    
    # Patterns for high-confidence queries
    HIGH_CONFIDENCE_PATTERNS = {
        'jenkins': [
            r'jenkins.*meeshogcp\.in',
            r'build.*failed',
            r'ci/cd.*failed',
            r'console.*log',
            r'job.*failed',
            r'pipeline.*failed'
        ],
        'github': [
            r'github\.com.*pull',
            r'github\.com.*issues',
            r'pr.*#\d+',
            r'pull.*request',
            r'merge.*conflict',
            r'ci.*check.*failed'
        ],
        'kubernetes': [
            r'pod.*crash',
            r'namespace.*error',
            r'deployment.*failed',
            r'health.*check.*failed',
            r'k8s.*issue',
            r'kubernetes.*problem'
        ]
    }
    
    # Patterns for low-confidence queries
    LOW_CONFIDENCE_PATTERNS = [
        r'access.*request',
        r'permission.*grant',
        r'user.*management',
        r'account.*setup',
        r'login.*issue',
        r'password.*reset',
        r'business.*requirement',
        r'evaluation.*request'
    ]
    
    @staticmethod
    def detect_confidence(query: str) -> Dict[str, Any]:
        """
        Detect confidence level for a DevOps analysis query
        
        Args:
            query: The user query to analyze
            
        Returns:
            Dict containing confidence information
        """
        query_lower = query.lower()
        
        # Check for low-confidence patterns first
        for pattern in ConfidenceDetector.LOW_CONFIDENCE_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return {
                    "confidence": False,
                    "confidence_level": "low",
                    "reasoning": "Query appears to be about access/permissions rather than DevOps issues",
                    "detected_type": "access_request"
                }
        
        # Check for high-confidence patterns
        detected_types = []
        confidence_scores = []
        
        for query_type, patterns in ConfidenceDetector.HIGH_CONFIDENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    detected_types.append(query_type)
                    confidence_scores.append(1.0)
                    break
        
        # Use URL detection as additional signal
        url_type = Detector.detect_url_type(query)
        if url_type != "general":
            detected_types.append(url_type)
            confidence_scores.append(0.9)
        
        # Determine overall confidence
        if detected_types:
            # High confidence if we detected specific DevOps patterns
            confidence_level = "high" if max(confidence_scores) >= 0.9 else "medium"
            reasoning = f"Detected {', '.join(set(detected_types))} patterns in query"
            
            return {
                "confidence": True,
                "confidence_level": confidence_level,
                "reasoning": reasoning,
                "detected_type": detected_types[0] if detected_types else "unknown"
            }
        else:
            # Check for general DevOps keywords
            devops_keywords = [
                'build', 'deploy', 'deployment', 'crash', 'error', 'failed', 
                'issue', 'problem', 'debug', 'troubleshoot', 'health', 'status'
            ]
            
            keyword_matches = [kw for kw in devops_keywords if kw in query_lower]
            
            if keyword_matches:
                return {
                    "confidence": True,
                    "confidence_level": "medium",
                    "reasoning": f"Contains DevOps keywords: {', '.join(keyword_matches[:3])}",
                    "detected_type": "general_devops"
                }
            else:
                return {
                    "confidence": False,
                    "confidence_level": "low",
                    "reasoning": "No clear DevOps patterns or keywords detected",
                    "detected_type": "unknown"
                }
    
    @staticmethod
    def get_confidence_reasoning(confidence_info: Dict[str, Any]) -> str:
        """Get human-readable confidence reasoning"""
        return confidence_info.get("reasoning", "No reasoning provided")
    
    @staticmethod
    def should_analyze(query: str) -> bool:
        """Quick check if query should be analyzed"""
        confidence_info = ConfidenceDetector.detect_confidence(query)
        return confidence_info["confidence"]
    
    @staticmethod
    def get_analysis_priority(query: str) -> str:
        """Get analysis priority based on confidence and detected type"""
        confidence_info = ConfidenceDetector.detect_confidence(query)
        
        if not confidence_info["confidence"]:
            return "low"
        
        confidence_level = confidence_info["confidence_level"]
        detected_type = confidence_info.get("detected_type", "unknown")
        
        # High priority for specific tool issues
        if detected_type in ["jenkins", "github", "kubernetes"] and confidence_level == "high":
            return "high"
        elif confidence_level == "high":
            return "medium"
        else:
            return "low"