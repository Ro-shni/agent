#!/usr/bin/env python3
"""
Test script for MongoDB RAG Service
Demonstrates historical solution retrieval based on user queries
"""

import asyncio
import os
from dotenv import load_dotenv
from utils.rag_service import MongoDBRAGService
from config import Settings

async def test_rag_service():
    """Test the RAG service with sample queries"""
    
    # Load environment variables
    load_dotenv()
    
    print("🧪 Testing MongoDB RAG Service")
    print("=" * 50)
    
    # Initialize RAG service
    mongo_config = Settings.get_mongodb_config()
    rag_service = MongoDBRAGService(
        mongo_uri=mongo_config["uri"],
        database=mongo_config["database"],
        collection=mongo_config["collection"],
        timeout=mongo_config["timeout"]
    )
    
    # Initialize the service
    success = await rag_service.initialize()
    if not success:
        print("❌ Failed to initialize RAG service")
        return
    
    print("✅ RAG service initialized successfully!")
    print()
    
    # Test queries
    test_queries = [
        "App works in pre-prod but fails in prod due to config issues",
        "supplier-ums application startup errors",
        "deployment configuration problems",
        "health check failures in production",
        "memory issues causing pod crashes",
        "turbo turtle check is failing in this PR: https://github.com/Meesho/OrderService/pull/839 , this is blocking deployment. Pls help",
        "facing problem with github, unable to do 2FA",
        "This PR is stuck: https://github.com/Meesho/dev-ops-buddy-frontend/pull/159",
        "unable to promote these two canary from long time, can you please check? https://argocd-demand-prd.meeshogcp.in/applications/argocd-demand-prd/prd-affiliate-consumer?resource= https://argocd-demand-prd.meeshogcp.in/applications/argocd-demand-prd/prd-affiliate-mq-consumer?resource="
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"🔍 Test Query {i}: {query}")
        print("-" * 40)
        
        # Get historical solutions
        solutions = await rag_service.get_historical_solutions(query)
        
        if solutions.get("solutions_found"):
            print(f"✅ {solutions['message']}")
            
            # Show top solutions
            recommended_solutions = solutions.get("recommended_solutions", [])
            if recommended_solutions:
                print(f"\n📚 Top Historical Solutions:")
                for j, solution in enumerate(recommended_solutions[:3], 1):
                    jira_id = solution.get("jira_id", "Unknown")
                    similarity = solution.get("similarity_score", 0.0)
                    solution_text = solution.get("solution", "")
                    print(f"   {j}. [{jira_id}] (Similarity: {similarity:.2f})")
                    print(f"      {solution_text[:150]}...")
                    print()
            
            # Show recommendations
            recommendations = solutions.get("recommendations", [])
            if recommendations:
                print(f"💡 AI Recommendations:")
                for rec in recommendations[:3]:
                    print(f"   - {rec}")
        else:
            print(f"❌ {solutions['message']}")
        
        print("\n" + "=" * 50 + "\n")
    
    # Close the service
    rag_service.close()
    print("✅ RAG service test completed!")

if __name__ == "__main__":
    asyncio.run(test_rag_service())
