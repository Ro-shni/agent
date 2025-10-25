#!/usr/bin/env python3
"""
Test script to verify RAG service integration with the orchestrator
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import backend modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from backend.core.orchestrator import UnifiedDevOpsOrchestrator

async def test_rag_orchestrator_integration():
    """Test RAG service integration with the orchestrator"""
    print("🧪 Testing RAG Service Integration with Orchestrator")
    print("=" * 60)
    
    # Initialize orchestrator
    print("\n1. Initializing Orchestrator...")
    orchestrator = UnifiedDevOpsOrchestrator()
    await orchestrator.initialize()
    
    if not orchestrator.initialized:
        print("❌ Orchestrator initialization failed!")
        return
    
    print("✅ Orchestrator initialized successfully!")
    
    # Test queries that should trigger RAG
    test_queries = [
        #"Health check failures in stg-bug-buster namespace - pods are not responding to probes",
        "This PR is stuck: https://github.com/Meesho/Bug-Buster-Bot/pull/54 - health checks are failing"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*60}")
        print(f"🔍 Test Query {i}: {query}")
        print(f"{'='*60}")
        
        try:
            # Execute analysis
            result = await orchestrator.execute(user_prompt=query)
            
            # Check status
            status = result.get('status', 'unknown')
            print(f"📊 Status: {status}")
            
            # Check if RAG was used by looking for historical solutions in the summary
            summary = result.get('summary', '')
            if 'HISTORICAL SOLUTIONS FOUND' in summary or '📚' in summary:
                print("✅ RAG service was used in this analysis")
                # Extract and show RAG results from summary
                lines = summary.split('\n')
                in_rag_section = False
                for line in lines:
                    if 'HISTORICAL SOLUTIONS FOUND' in line or '📚' in line:
                        in_rag_section = True
                    if in_rag_section and line.strip():
                        print(f"   {line}")
                        if line.strip().startswith('🟢') or line.strip().startswith('🟡') or line.strip().startswith('🔴'):
                            break
            else:
                print("⚠️ RAG not used in this analysis")
            
            # Show execution path
            execution_history = result.get('execution_history', [])
            if execution_history:
                print(f"\n🔄 Execution Path:")
                for step in execution_history:
                    agent = step.get('agent', 'unknown').upper()
                    action = step.get('action', 'unknown')
                    print(f"   • {agent}: {action}")
            
            # Show summary
            summary = result.get('summary', 'No summary')
            print(f"\n📝 Summary: {summary[:200]}...")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    # Cleanup
    print(f"\n{'='*60}")
    print("🧹 Cleaning up...")
    orchestrator.cleanup()
    print("✅ Test completed!")

if __name__ == "__main__":
    asyncio.run(test_rag_orchestrator_integration())
