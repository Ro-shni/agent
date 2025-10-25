"""
Handles Kubernetes cluster and context management.
"""
import subprocess
from typing import Dict, Any, Optional

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
            print(f"   🔍 Environment: {environment}")
            for context in contexts:
                print(f"   🔍 Context: {context}")
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
        
        # Special case for shared int
        if environment == "int":
            for context in contexts:
                if "shared-int" in context:
                    return context
        
        return None

    @staticmethod
    async def handle_cluster_switching_fixed(namespace_info: Dict[str, Any]) -> bool:
        """FIXED: Handle cluster context switching with proper error handling"""
        target_context = namespace_info.get("cluster_context_needed")
        
        if not target_context:
            print("   ⚠️ No cluster context switching needed")
            return False
        
        try:
            current_context_info = SmartClusterManager.get_current_context()
            current_context = current_context_info.get("current_context", "unknown")
            
            print(f"   📍 Current context: {current_context}")
            print(f"   🎯 Target context: {target_context}")
            
            if target_context != current_context:
                print(f"   🔄 Switching cluster context...")
                switch_result = SmartClusterManager.switch_context(target_context)
                
                if switch_result.get("success"):
                    print(f"   ✅ Successfully switched to: {target_context}")
                    return True
                else:
                    print(f"   ❌ Failed to switch context: {switch_result.get('error')}")
                    print(f"   ℹ️ Continuing with current context: {current_context}")
                    return False
            else:
                print(f"   ✅ Already on correct context")
                return False
        except Exception as e:
            print(f"   ❌ Cluster switching error: {str(e)}")
            print(f"   ℹ️ Continuing with current context")
            return False

