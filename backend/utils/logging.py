import json
from typing import Dict, Any


class ToolCallLogger:
    """Real-time tool call streaming logger"""
    
    @staticmethod
    def log_tool_call(tool_name: str, parameters: Dict[str, Any], step: int):
        """Log tool call in real-time"""
        print(f"\n🔧 TOOL CALL #{step}: {tool_name}")
        print(f"📋 Parameters: {json.dumps(parameters, indent=2)}")
        print(f"⏳ Executing...")
    
    @staticmethod
    def log_tool_result(tool_name: str, result_summary: str, step: int):
        """Log tool result"""
        print(f"✅ Result: {result_summary}")
        print(f"⏱️ Tool call #{step} completed")
    
    @staticmethod
    def log_analysis_step(step_name: str, description: str):
        """Log analysis step"""
        print(f"\n🔍 DEVOPS STEP: {step_name}")
        print(f"📝 {description}")


