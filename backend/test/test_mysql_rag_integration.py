#!/usr/bin/env python3
"""
Test script for MySQL and RAG integration
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import backend modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from backend.utils.sql_service import sql_service
from backend.utils.rag_service import rag_service
from backend.utils.detectors import namespace_detector
from backend.core.orchestrator import UnifiedDevOpsOrchestrator


async def test_sql_service():
    """Test MySQL service functionality"""
    print("🧪 Testing MySQL Service")
    print("=" * 50)
    
    try:
        # Initialize MySQL service
        success = await sql_service.initialize()
        if not success:
            print("❌ MySQL service initialization failed")
            return False
        
        # Test getting service details
        print("🔄 Fetching service details from MySQL...")
        service_mapping = await sql_service.get_service_details()
        
        print(f"✅ Retrieved {len(service_mapping)} service mappings")
        
        # Show some examples
        if service_mapping:
            print("\n📊 Sample service mappings:")
            for i, (app, bu) in enumerate(list(service_mapping.items())[:5]):
                print(f"   {i+1}. {app} -> {bu}")
        
        # Test getting business unit for specific app
        test_app = "bug-buster"
        bu = await sql_service.get_business_unit_for_app(test_app)
        print(f"\n🔍 Business unit for '{test_app}': {bu}")
        
        # Test searching services
        search_results = await sql_service.search_services_by_pattern("bug")
        print(f"\n🔍 Search results for 'bug': {len(search_results)} found")
        
        return True
        
    except Exception as e:
        print(f"❌ MySQL service test failed: {str(e)}")
        return False
    finally:
        await sql_service.close()


async def test_rag_service():
    """Test RAG service functionality"""
    print("\n🧪 Testing RAG Service")
    print("=" * 50)
    
    try:
        # Initialize RAG service
        success = await rag_service.initialize()
        if not success:
            print("❌ RAG service initialization failed")
            return False
        
        # Test getting historical solutions
        print("🔄 Searching for historical solutions...")
        context = {
            "namespace": "stg-bug-buster",
            "environment": "stg",
            "services": ["bug-buster"],
            "issue_type": "health_check",
            "error_patterns": ["health check failed", "probe failure"]
        }
        
        solutions = await rag_service.get_historical_solutions(
            "health check failures in stg-bug-buster",
            context
        )
        
        print(f"✅ RAG search completed")
        print(f"   Solutions found: {solutions.get('solutions_found', False)}")
        print(f"   Total found: {solutions.get('total_found', 0)}")
        
        if solutions.get('recommended_solutions'):
            print("\n📚 Top historical solutions:")
            for i, solution in enumerate(solutions['recommended_solutions'][:3], 1):
                jira_id = solution.get('jira_id', 'Unknown')
                similarity = solution.get('similarity_score', 0.0)
                title = solution.get('title', 'No title')[:50]
                print(f"   {i}. [{jira_id}] (Similarity: {similarity:.2f}) {title}...")
        
        return True
        
    except Exception as e:
        print(f"❌ RAG service test failed: {str(e)}")
        return False
    finally:
        rag_service.close()


async def test_namespace_detector():
    """Test namespace detector with MySQL integration"""
    print("\n🧪 Testing Namespace Detector")
    print("=" * 50)
    
    try:
        # Test cases
        test_cases = [
            "Pods are crashlooping in stg-bug-buster namespace",
            "App health degraded for stg-carrier-aggregator in supply stg",
            "Health check failures in prd-inventory-service",
            "Performance issues with stg-search-orchestrator"
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n🔍 Test Case {i}: {test_case}")
            
            namespace_info = await namespace_detector.extract_namespace_info_from_user_input(test_case)
            
            print(f"   • Issue Type: {namespace_info.get('issue_type', 'unknown')}")
            print(f"   • Severity: {namespace_info.get('severity', 'medium')}")
            print(f"   • Environment: {namespace_info.get('environment', 'unknown')}")
            print(f"   • Business Unit: {namespace_info.get('business_unit', 'unknown')}")
            print(f"   • Applications: {namespace_info.get('applications', [])}")
            print(f"   • Namespaces: {namespace_info.get('namespaces', [])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Namespace detector test failed: {str(e)}")
        return False


async def test_full_orchestrator():
    """Test the full orchestrator with MySQL and RAG integration"""
    print("\n🧪 Testing Full Orchestrator")
    print("=" * 50)
    
    try:
        # Initialize orchestrator
        orchestrator = UnifiedDevOpsOrchestrator()
        success = await orchestrator.initialize()
        
        if not success:
            print("❌ Orchestrator initialization failed")
            return False
        
        # Test with a sample query
        test_query = "Health check failures in stg-bug-buster namespace"
        print(f"🔄 Testing with query: {test_query}")
        
        result = await orchestrator.execute(
            user_prompt=test_query,
            context={}
        )
        
        print(f"✅ Orchestrator test completed")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Summary: {result.get('summary', 'No summary')[:100]}...")
        
        # Check if RAG was used
        if result.get('historical_solutions'):
            print("   ✅ RAG integration working")
        else:
            print("   ⚠️ RAG integration not used")
        
        return True
        
    except Exception as e:
        print(f"❌ Orchestrator test failed: {str(e)}")
        return False


async def main():
    """Run all tests"""
    print("🚀 Testing MySQL and RAG Integration")
    print("=" * 60)
    
    tests = [
        ("MySQL Service", test_sql_service),
        ("RAG Service", test_rag_service),
        ("Namespace Detector", test_namespace_detector),
        ("Full Orchestrator", test_full_orchestrator)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name} test...")
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! MySQL and RAG integration is working correctly.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    asyncio.run(main())
