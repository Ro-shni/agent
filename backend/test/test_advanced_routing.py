#!/usr/bin/env python3
"""
Advanced test script for intelligent routing scenarios
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import backend modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from backend.core.orchestrator import UnifiedDevOpsOrchestrator

async def test_health_check_routing():
    """Test routing when health checks are failing"""
    
    print("🧪 Testing Health Check Failure Routing")
    print("=" * 60)
    
    orchestrator = UnifiedDevOpsOrchestrator()
    await orchestrator.initialize()
    
    # Test cases that should trigger GitHub -> K8s routing
    test_cases = [
        {
            "name": "GitHub PR with Health Check Keywords",
            "prompt": "This PR is stuck: https://github.com/Meesho/search-orchestrator/pull/2006 - health checks are failing",
            "should_route_to_k8s": True
        },
        {
            "name": "GitHub PR with Probe Failures",
            "prompt": "PR 123 has liveness probe failures and readiness probe issues",
            "should_route_to_k8s": True
        },
        {
            "name": "GitHub PR with Deployment Issues",
            "prompt": "This PR has deployment failures and pods are not starting properly",
            "should_route_to_k8s": True
        },
        {
            "name": "GitHub PR with K8s Keywords",
            "prompt": "PR 456 has kubernetes deployment issues and pod crashes",
            "should_route_to_k8s": True
        },
        {
            "name": "GitHub PR with CI/CD Success",
            "prompt": "This PR is working fine: https://github.com/Meesho/search-orchestrator/pull/2006 - all checks passed",
            "should_route_to_k8s": False
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test Case {i}: {test_case['name']}")
        print(f"📝 Prompt: {test_case['prompt']}")
        print(f"🎯 Should route to K8s: {test_case['should_route_to_k8s']}")
        print("-" * 40)
        
        try:
            result = await orchestrator.execute(
                user_prompt=test_case['prompt'],
                context={}
            )
            
            # Extract execution path
            execution_history = result.get("execution_history", [])
            agents_executed = [step.get("agent") for step in execution_history if step.get("agent") != "orchestrator"]
            
            print(f"🔄 Agents Executed: {agents_executed}")
            
            # Check if routing worked as expected
            routed_to_k8s = "kubernetes" in agents_executed
            expected = test_case['should_route_to_k8s']
            
            if routed_to_k8s == expected:
                print(f"✅ PASS: Routing worked as expected")
            else:
                print(f"❌ FAIL: Expected K8s routing: {expected}, Got: {routed_to_k8s}")
            
            # Show routing decision reasoning
            if "github" in agents_executed and "kubernetes" in agents_executed:
                print("🔍 GitHub -> Kubernetes routing triggered")
                
                # Check if it was due to health check keywords
                user_prompt_lower = test_case['prompt'].lower()
                health_keywords = ["health", "probe", "deployment", "k8s", "kubernetes", "pod", "crash"]
                found_keywords = [kw for kw in health_keywords if kw in user_prompt_lower]
                if found_keywords:
                    print(f"   • Triggered by keywords: {found_keywords}")
            
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
        
        print("=" * 60)
    
    orchestrator.cleanup()

async def test_kubernetes_issue_detection():
    """Test Kubernetes issue detection and routing"""
    
    print("\n🧪 Testing Kubernetes Issue Detection")
    print("=" * 60)
    
    orchestrator = UnifiedDevOpsOrchestrator()
    await orchestrator.initialize()
    
    # Test cases that should route directly to Kubernetes
    test_cases = [
        {
            "name": "Pod Crashloop",
            "prompt": "Pods are crashlooping in stg-bug-buster namespace",
            "expected_route": "kubernetes"
        },
        {
            "name": "Health Check Degraded",
            "prompt": "App health degraded for stg-carrier-aggregator in supply stg",
            "expected_route": "kubernetes"
        },
        {
            "name": "Pod Restart Issues",
            "prompt": "Pods keep restarting in prd-payment-service namespace",
            "expected_route": "kubernetes"
        },
        {
            "name": "Deployment Issues",
            "prompt": "Deployment is failing in stg-user-service",
            "expected_route": "kubernetes"
        },
        {
            "name": "Resource Issues",
            "prompt": "Pods are running out of memory in stg-analytics namespace",
            "expected_route": "kubernetes"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test Case {i}: {test_case['name']}")
        print(f"📝 Prompt: {test_case['prompt']}")
        print(f"🎯 Expected Route: {test_case['expected_route']}")
        print("-" * 40)
        
        try:
            result = await orchestrator.execute(
                user_prompt=test_case['prompt'],
                context={}
            )
            
            # Extract execution path
            execution_history = result.get("execution_history", [])
            agents_executed = [step.get("agent") for step in execution_history if step.get("agent") != "orchestrator"]
            
            print(f"🔄 Agents Executed: {agents_executed}")
            
            # Check if routing worked as expected
            if test_case['expected_route'] in agents_executed:
                print(f"✅ PASS: Correctly routed to {test_case['expected_route']}")
            else:
                print(f"❌ FAIL: Expected {test_case['expected_route']}, got {agents_executed}")
            
            # Show namespace detection
            kubernetes_response = result.get("kubernetes_response")
            if kubernetes_response:
                findings = kubernetes_response.findings
                namespace = findings.get("namespace", "Unknown")
                issue_type = findings.get("issue_type", "Unknown")
                severity = findings.get("severity", "Unknown")
                print(f"   • Namespace: {namespace}")
                print(f"   • Issue Type: {issue_type}")
                print(f"   • Severity: {severity}")
            
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
        
        print("=" * 60)
    
    orchestrator.cleanup()

async def test_jenkins_routing():
    """Test Jenkins routing scenarios"""
    
    print("\n🧪 Testing Jenkins Routing")
    print("=" * 60)
    
    orchestrator = UnifiedDevOpsOrchestrator()
    await orchestrator.initialize()
    
    # Test cases for Jenkins routing
    test_cases = [
        {
            "name": "Jenkins Build Failure",
            "prompt": "Jenkins build failed for stg-carrier-aggregator",
            "expected_route": "jenkins"
        },
        {
            "name": "CI/CD Pipeline Issues",
            "prompt": "CI/CD pipeline is failing for the payment service",
            "expected_route": "jenkins"
        },
        {
            "name": "Build Console Issues",
            "prompt": "Check the Jenkins console for build errors",
            "expected_route": "jenkins"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test Case {i}: {test_case['name']}")
        print(f"📝 Prompt: {test_case['prompt']}")
        print(f"🎯 Expected Route: {test_case['expected_route']}")
        print("-" * 40)
        
        try:
            result = await orchestrator.execute(
                user_prompt=test_case['prompt'],
                context={}
            )
            
            # Extract execution path
            execution_history = result.get("execution_history", [])
            agents_executed = [step.get("agent") for step in execution_history if step.get("agent") != "orchestrator"]
            
            print(f"🔄 Agents Executed: {agents_executed}")
            
            # Check if routing worked as expected
            if test_case['expected_route'] in agents_executed:
                print(f"✅ PASS: Correctly routed to {test_case['expected_route']}")
            else:
                print(f"❌ FAIL: Expected {test_case['expected_route']}, got {agents_executed}")
            
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
        
        print("=" * 60)
    
    orchestrator.cleanup()

if __name__ == "__main__":
    asyncio.run(test_health_check_routing())
    asyncio.run(test_kubernetes_issue_detection())
    asyncio.run(test_jenkins_routing())
