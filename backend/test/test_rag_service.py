#!/usr/bin/env python3
"""
Test script for RAG service functionality
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import backend modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from backend.utils.rag_service import rag_service

async def test_rag_service():
    """Test RAG service functionality"""
    print("🧪 Testing RAG Service")
    print("=" * 50)
    
    # Test 1: Initialize RAG service
    print("\n1. Testing RAG Service Initialization...")
    success = await rag_service.initialize()
    
    if success:
        print("✅ RAG Service initialized successfully!")
    else:
        print("❌ RAG Service initialization failed!")
        return
    
    # Test 2: Test historical solutions retrieval
    print("\n2. Testing Historical Solutions Retrieval...")
    
    test_queries = [
        "App works in pre-prod but fails in prod due to config issues",
        "supplier-ums health check failures in central stg cluster",
        "Pods crashlooping in stg-bug-buster namespace due to memory issues",
        "This PR is stuck: https://github.com/Meesho/search-orchestrator/pull/2006"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n   Test Query {i}: {query}")
        print("   " + "-" * 40)
        
        try:
            # Test with context
            context = {
                "namespace": "stg-bug-buster",
                "environment": "stg",
                "services": ["bug-buster"],
                "issue_type": "health_check"
            }
            
            result = await rag_service.get_historical_solutions(query, context)
            
            print(f"   Status: {result.get('solutions_found', False)}")
            print(f"   Message: {result.get('message', 'No message')}")
            
            solutions = result.get('recommended_solutions', [])
            if solutions:
                print(f"   Found {len(solutions)} solutions:")
                for j, solution in enumerate(solutions[:2], 1):  # Show top 2
                    jira_id = solution.get('jira_id', 'Unknown')
                    similarity = solution.get('similarity_score', 0.0)
                    solution_text = solution.get('solution', '')[:100]
                    print(f"     {j}. [{jira_id}] (Similarity: {similarity:.2f})")
                    print(f"        {solution_text}...")
            else:
                print("   No solutions found")
            
            recommendations = result.get('recommendations', [])
            if recommendations:
                print(f"   Recommendations: {len(recommendations)}")
                for rec in recommendations[:2]:  # Show top 2
                    print(f"     - {rec}")
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    # Test 3: Test without context
    print("\n3. Testing without context...")
    try:
        result = await rag_service.get_historical_solutions("health check failures", None)
        print(f"   Status: {result.get('solutions_found', False)}")
        print(f"   Message: {result.get('message', 'No message')}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    # Cleanup
    print("\n4. Cleaning up...")
    rag_service.close()
    print("✅ RAG Service test completed!")

if __name__ == "__main__":
    asyncio.run(test_rag_service())
