#!/usr/bin/env python3
"""
Test script for intelligent routing in the backend module
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import backend modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from backend.core.orchestrator import UnifiedDevOpsOrchestrator

async def test_routing_scenarios():
    """Test various routing scenarios"""
    
    print("🧪 Testing Intelligent Routing Scenarios")
    print("=" * 60)
    
    # Initialize orchestrator
    orchestrator = UnifiedDevOpsOrchestrator()
    await orchestrator.initialize()
    
    # Test scenarios
    test_cases = [
        {
            "name": "GitHub PR with Health Check Failures",
            "prompt": "This PR is stuck: https://github.com/Meesho/Bug-Buster-Bot/pull/54",
            "expected_route": "github -> kubernetes"
        },
       
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test Case {i}: {test_case['name']}")
        print(f"📝 Prompt: {test_case['prompt']}")
        print(f"🎯 Expected: {test_case['expected_route']}")
        print("-" * 40)
        
        try:
            # Execute the workflow
            result = await orchestrator.execute(
                user_prompt=test_case['prompt'],
                context={}
            )
            
            # Extract execution path
            execution_history = result.get("execution_history", [])
            print(f"🔄 Actual Execution Path:")
            for step in execution_history:
                agent = step.get("agent", "unknown").upper()
                action = step.get("action", "unknown")
                print(f"   • {agent}: {action}")
            
            # Check if routing worked as expected
            agents_executed = [step.get("agent") for step in execution_history if step.get("agent") != "orchestrator"]
            actual_route = " -> ".join(agents_executed) if agents_executed else "none"
            
            print(f"✅ Actual Route: {actual_route}")
            
            # Simple validation
            if "github" in test_case['expected_route'] and "github" in actual_route:
                print("✅ GitHub routing detected correctly")
            if "kubernetes" in test_case['expected_route'] and "kubernetes" in actual_route:
                print("✅ Kubernetes routing detected correctly")
            if "jenkins" in test_case['expected_route'] and "jenkins" in actual_route:
                print("✅ Jenkins routing detected correctly")
            
            print(f"📊 Summary: {result.get('summary', 'No summary')[:100]}...")
            
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
        
        print("=" * 60)
    
    # Cleanup
    orchestrator.cleanup()
    print("\n🎉 Routing tests completed!")

async def test_github_to_k8s_routing():
    """Specifically test GitHub to Kubernetes routing"""
    
    print("\n🧪 Testing GitHub to Kubernetes Routing")
    print("=" * 60)
    
    orchestrator = UnifiedDevOpsOrchestrator()
    await orchestrator.initialize()
    
    # Test case that should trigger GitHub -> K8s routing
    test_prompt = "https://github.com/Meesho/Bug-Buster-Bot/pull/54"
    
    print(f"📝 Testing: {test_prompt}")
    
    try:
        result = await orchestrator.execute(
            user_prompt=test_prompt,
            context={}
        )
        
        # Check execution path
        execution_history = result.get("execution_history", [])
        agents_executed = [step.get("agent") for step in execution_history if step.get("agent") != "orchestrator"]
        
        print(f"🔄 Agents Executed: {agents_executed}")
        
        # Check if both GitHub and Kubernetes were executed
        if "github" in agents_executed and "kubernetes" in agents_executed:
            print("✅ SUCCESS: GitHub -> Kubernetes routing worked!")
        else:
            print("❌ FAILED: GitHub -> Kubernetes routing did not work")
            print(f"   Expected: ['github', 'kubernetes']")
            print(f"   Actual: {agents_executed}")
        
        # Show findings
        github_response = result.get("github_response")
        kubernetes_response = result.get("kubernetes_response")
        
        if github_response:
            print(f"\n📊 GitHub Findings:")
            findings = github_response.findings
            ci_analysis = findings.get("ci_analysis", {})
            print(f"   • CI Status: {ci_analysis.get('status', 'Unknown')}")
            print(f"   • Has Failures: {ci_analysis.get('has_failures', False)}")
            print(f"   • Failing Checks: {len(ci_analysis.get('failing_checks', []))}")
        
        if kubernetes_response:
            print(f"\n☸️ Kubernetes Findings:")
            findings = kubernetes_response.findings
            print(f"   • Namespace: {findings.get('namespace', 'Unknown')}")
            print(f"   • Unhealthy Pods: {len(findings.get('unhealthy_pods', []))}")
            print(f"   • Root Causes: {len(findings.get('root_causes', []))}")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
    
    orchestrator.cleanup()

if __name__ == "__main__":
    asyncio.run(test_routing_scenarios())
    asyncio.run(test_github_to_k8s_routing())
