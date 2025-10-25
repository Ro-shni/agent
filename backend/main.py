"""
Main entry point for Kairos - Interactive Mode Only
"""
import asyncio
from .core.orchestrator import UnifiedDevOpsOrchestrator
from dotenv import load_dotenv
load_dotenv()

async def interactive_mode():
    """Interactive CLI mode for DevOps analysis"""
    
    print("🎯 Unified DevOps Multi-Agent Interactive Mode - COMPLETELY FIXED")
    print("=" * 70)
    print("INTELLIGENT EXAMPLES:")
    print("- 'PR 51 health check failures in central stg cluster'")
    print("- 'App health degraded for stg-carrier-aggregator in supply stg'")
    print("- 'Pods crashlooping in stg-bug-buster namespace'")
    print("- 'This PR is stuck: https://github.com/org/repo/pull/123'")
    print("- 'Give me pod events for stg-bug-buster in central stg cluster'")
    print("\nCOMPLETELY FIXED FEATURES:")
    print("✅ Fixed GitHub→K8s routing (only routes if real health issues)")
    print("✅ Fixed business unit detection ('central stg cluster' works)")
    print("✅ Fixed cluster context switching")
    print("✅ Intelligent concise summaries")
    print("✅ Real GitHub analysis (not hardcoded)")
    print("✅ Production-ready error handling")
    print("Type 'quit' to exit")
    print("=" * 70)
    
    # Initialize orchestrator
    orchestrator = UnifiedDevOpsOrchestrator()
    await orchestrator.initialize()
    
    while True:
        try:
            user_input = input("\n💬 Describe the issue: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Execute intelligent workflow
            result = await orchestrator.execute(
                user_prompt=user_input,
                context={}
            )
            
            # Show execution path (CONCISE)
            execution_history = result.get("execution_history", [])
            if execution_history:
                print(f"\n🔄 EXECUTION PATH:")
                for step in execution_history:
                    agent = step.get("agent", "unknown").upper()
                    action = step.get("action", "unknown")
                    print(f"   {step.get('step')}. {agent}: {action}")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    # Cleanup
    orchestrator.cleanup()



async def main():
    """Main function - Interactive mode only"""
    await interactive_mode()

if __name__ == "__main__":
    asyncio.run(main())