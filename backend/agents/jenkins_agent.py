"""
Jenkins Agent - Modular version based on gptjenk.py
Handles Jenkins build failure analysis and CI/CD pipeline debugging
"""

import re
import base64
import aiohttp
from typing import Dict, Any, List, Optional
from langchain_openai import AzureChatOpenAI

from ..config.settings import Settings
from ..utils.logging import ToolCallLogger
from ..utils.confidence_detector import ConfidenceDetector

class JenkinsAgent:
    """Jenkins build failure analysis and CI/CD debugging agent"""
    
    def __init__(self, llm: AzureChatOpenAI, tool_logger: ToolCallLogger, rag_service=None):
        self.llm = llm
        self.tool_logger = tool_logger
        self.rag_service = rag_service
        self.initialized = False
    
    async def initialize(self) -> bool:
        """Initialize Jenkins agent"""
        try:
            print("🔄 Initializing Jenkins agent...")
            self.initialized = True
            print("✅ Jenkins agent initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Jenkins agent initialization failed: {str(e)}")
            return False
    
    async def analyze(self, user_prompt: str) -> Dict[str, Any]:
        """Main analysis method for Jenkins issues"""
        
        if not self.initialized:
            await self.initialize()
        
        print("🏗️ Jenkins Agent: Starting build failure analysis...")
        
        try:
            # Extract Jenkins URL from user prompt
            jenkins_url = self._extract_jenkins_url(user_prompt)
            
            if not jenkins_url:
                return {
                    "status": "failed",
                    "error": "Could not extract Jenkins URL from request",
                    "suggestions": [
                        "Provide a Jenkins build URL (e.g., https://jenkins-prd.meeshogcp.in/job/.../console)",
                        "Include the full Jenkins console URL in your request"
                    ]
                }
            
            print(f"🏗️ Detected Jenkins URL: {jenkins_url}")
            
            # Parse Jenkins URL
            parsed_info = self._parse_jenkins_url(jenkins_url)
            if not parsed_info:
                return {
                    "status": "failed",
                    "error": "Invalid Jenkins URL format",
                    "suggestions": ["Provide a valid Jenkins console URL"]
                }
            
            print(f"🏗️ Environment: {parsed_info['env']}")
            print(f"🏗️ Job Path: {parsed_info['job_path']}")
            print(f"🏗️ Build Number: {parsed_info['build_number']}")
            
            # Fetch build information and logs
            build_data = await self._fetch_jenkins_build_info(
                parsed_info['env'], 
                parsed_info['job_path'], 
                parsed_info['build_number'],
                jenkins_url
            )
            
            if not build_data:
                return {
                    "status": "failed",
                    "error": "Failed to fetch Jenkins build information",
                    "suggestions": ["Check Jenkins URL accessibility", "Verify build exists"]
                }
            
            # Analyze the failure with LLM
            analysis = await self._analyze_failure_with_llm(
                build_data['build_info'], 
                build_data['build_logs'],
                parsed_info
            )
            
            # Get RAG solution based on problem and root cause
            rag_solution = await self._get_rag_solution(
                analysis.get("problem_identified", ""),
                analysis.get("root_cause", ""),
                user_prompt
            )
            
            # Build detailed analysis text
            analysis_text = self._build_detailed_analysis(
                build_data['build_info'], 
                analysis, 
                parsed_info
            )
            
            # Get confidence information
            confidence_info = ConfidenceDetector.detect_confidence(user_prompt)
            
            return {
                "status": "success",
                "problem_identified": analysis.get("problem_identified", "Unknown problem"),
                "root_cause": analysis.get("root_cause", "Unknown root cause"),
                "solution": analysis.get("solution", "No solution provided"),
                "summary": analysis.get("summary", "No summary available"),
                "rag_solution": rag_solution,
                "analysis_text": analysis_text,
                "build_info": {
                    "environment": parsed_info['env'],
                    "job_path": parsed_info['job_path'],
                    "build_number": parsed_info['build_number'],
                    "build_status": build_data['build_info'].get('result', 'UNKNOWN'),
                    "build_url": jenkins_url
                },
                "confidence": confidence_info["confidence"],
                "confidence_level": confidence_info["confidence_level"],
                "confidence_reasoning": confidence_info["reasoning"]
            }
            
        except Exception as e:
            print(f"❌ Jenkins Agent error: {str(e)}")
            return {
                "status": "failed",
                "problem_identified": "Unable to analyze Jenkins build",
                "root_cause": f"Error: {str(e)}",
                "solution": [
                    "Check Jenkins connectivity",
                    "Verify build URL",
                    "Check network access",
                    "Verify authentication"
                ],
                "summary": f"Failed to analyze Jenkins build due to: {str(e)}"
            }
    
    def _extract_jenkins_url(self, user_prompt: str) -> Optional[str]:
        """Extract Jenkins URL from user prompt and redirect dev URLs to proxy"""
        # Pattern to match Jenkins URLs for all environments
        jenkins_pattern = r'https://jenkins-(?:prd|dev|dev-proxy)\.meeshogcp\.in/[^\s,]+'
        match = re.search(jenkins_pattern, user_prompt)
        if not match:
            return None
        
        url = match.group(0)
        
        # Clean up any trailing commas or extra characters
        url = url.rstrip(',/')
        
        # Redirect jenkins-dev URLs to jenkins-dev-proxy
        if "jenkins-dev.meeshogcp.in" in url and "jenkins-dev-proxy" not in url:
            url = url.replace("jenkins-dev.meeshogcp.in", "jenkins-dev-proxy.meeshogcp.in")
            print(f"🔄 Redirected jenkins-dev URL to jenkins-dev-proxy: {url}")
        
        # Ensure URL has /console suffix for proper Jenkins API access
        if not url.endswith('/console'):
            url = url.rstrip('/') + '/console'
            print(f"🔧 Added /console suffix to Jenkins URL: {url}")
        
        return url
    
    def _parse_jenkins_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Extract environment, job path, and build number from Jenkins URL
        Example: https://jenkins-dev.meeshogcp.in/job/feature-computation-service-cicd/job/develop/66/console
        """
        # Determine environment based on URL
        if "jenkins-prd" in url:
            env = "production"
        elif "jenkins-dev-proxy" in url:
            env = "dev-proxy"
        elif "jenkins-dev" in url:
            # This should not happen anymore due to redirection, but keep as fallback
            env = "dev-proxy"  # Treat as dev-proxy since we redirect dev to dev-proxy
        else:
            env = "dev-proxy"  # Default to dev-proxy for unknown URLs
            
        # Remove /console from URL for parsing
        clean_url = url.replace("/console", "")
        
        # Extract job path and build number
        # Pattern: /job/job1/job/job2/.../build_number (with optional trailing slash)
        match = re.search(r"/job/(.+)/(\d+)/?$", clean_url)
        if not match:
            return None

        job_path = match.group(1)
        build_number = match.group(2)

        return {"env": env, "job_path": job_path, "build_number": build_number}
    
    async def _fetch_jenkins_build_info(self, env: str, job_path: str, build_number: str, original_url: str) -> Optional[Dict[str, Any]]:
        """Fetch Jenkins build information and logs"""
        try:
            # Get Jenkins configuration from centralized config
            jenkins_config = Settings.get_jenkins_config()
            
            # Use centralized credentials based on environment
            if env == "production":
                base_url = jenkins_config["urls"]["production"]
                username = jenkins_config["credentials"]["production"]["username"]
                token = jenkins_config["credentials"]["production"]["token"]
            elif env == "dev-proxy":
                base_url = jenkins_config["urls"]["dev-proxy"]
                username = jenkins_config["credentials"]["dev-proxy"]["username"]
                token = jenkins_config["credentials"]["dev-proxy"]["token"]
            else:  # development
                base_url = jenkins_config["urls"]["development"]
                username = jenkins_config["credentials"]["development"]["username"]
                token = jenkins_config["credentials"]["development"]["token"]

            auth_str = f"{username}:{token}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            headers = {"Authorization": f"Basic {b64_auth}"}

            print(f"🏗️ Fetching build {build_number} from {env} ({job_path})")
            print(f"🏗️ Using base URL: {base_url}")

            # Create SSL context that doesn't verify certificates (like gptjenk.py)
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                # Build details
                build_url = f"{base_url}/job/{job_path}/{build_number}/api/json"
                async with session.get(build_url, headers=headers) as response:
                    if response.status != 200:
                        print(f"❌ Failed to fetch build info: {response.status}")
                        response_text = await response.text()
                        print(f"❌ Response text: {response_text}")
                        
                        # Special handling for development environment 401 errors
                        if response.status == 401 and "jenkins-dev" in base_url:
                            print(f"⚠️ Development Jenkins environment returned 401 Unauthorized")
                            print(f"⚠️ This might indicate the development environment requires different credentials")
                            print(f"⚠️ Or the development Jenkins instance might be down/restricted")
                            print(f"💡 Suggestion: Try using a production Jenkins URL instead")
                        
                        return None
                    build_info = await response.json()

                # Build logs
                log_url = f"{base_url}/job/{job_path}/{build_number}/consoleText"
                async with session.get(log_url, headers=headers) as response:
                    if response.status != 200:
                        print(f"❌ Failed to fetch build logs: {response.status}")
                        print(f"❌ Response text: {await response.text()}")
                        return None
                    build_logs = await response.text()

                return {
                    "build_info": build_info,
                    "build_logs": build_logs
                }

        except Exception as e:
            print(f"❌ Failed to fetch Jenkins build info: {str(e)}")
            return None
    
    async def _analyze_failure_with_llm(self, build_info: Dict[str, Any], logs: str, parsed_info: Dict[str, str]) -> Dict[str, Any]:
        """
        Send logs + metadata to Azure OpenAI for failure analysis using standardized format
        """
        try:
            # Use last 300 lines of logs as requested
            log_lines = logs.split('\n')
            if len(log_lines) > 300:
                truncated_logs = '\n'.join(log_lines[-300:])
                print(f"🔧 Using last 300 lines of logs (total: {len(log_lines)} lines)")
            else:
                truncated_logs = logs
                print(f"🔧 Using all {len(log_lines)} lines of logs")
            
            # Also truncate to 10000 chars for LLM context if needed
            if len(truncated_logs) > 10000:
                truncated_logs = truncated_logs[-10000:]
                print(f"🔧 Truncated logs to 10000 characters for LLM analysis")
            
            # Use the new standardized prompt format
            from ..prompts.jenkins import JENKINS_SYSTEM_PROMPT, get_jenkins_analysis_prompt
            
            build_data = {
                'environment': parsed_info.get('env', 'development'),
                'job_path': parsed_info.get('job_path', 'unknown'),
                'build_number': parsed_info.get('build_number', 'unknown'),
                'build_status': build_info.get('result', 'UNKNOWN'),
                'build_duration': build_info.get('duration', 0),
                'build_timestamp': build_info.get('timestamp', 'UNKNOWN'),
                'build_logs': truncated_logs
            }
            
            prompt = get_jenkins_analysis_prompt(build_data)

            response = await self.llm.ainvoke([{
                "role": "system", 
                "content": JENKINS_SYSTEM_PROMPT
            }, {
                "role": "user", 
                "content": prompt
            }])

            analysis_content = response.content
            
            # Parse the JSON response into structured format
            structured_analysis = self._parse_json_analysis(analysis_content, build_info)
            
            return structured_analysis

        except Exception as e:
            print(f"❌ LLM analysis failed: {str(e)}")
            return {
                "problem_identified": "Analysis failed",
                "root_cause": str(e),
                "solution": ["Retry analysis", "Check LLM configuration"],
                "summary": "Unable to analyze build failure due to technical error"
            }
    
    def _parse_json_analysis(self, analysis_content: str, build_info: Dict[str, Any]) -> Dict[str, Any]:
        """Parse JSON response from LLM into standardized format"""
        try:
            import json
            
            # Clean the response content
            content = analysis_content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            
            # Parse JSON
            parsed_analysis = json.loads(content)
            
            # Ensure all required fields are present
            return {
                "problem_identified": parsed_analysis.get("problem_identified", "Unknown problem"),
                "root_cause": parsed_analysis.get("root_cause", "Unknown root cause"),
                "solution": parsed_analysis.get("solution", "No solution provided"),
                "summary": parsed_analysis.get("summary", "No summary available")
            }
            
        except Exception as e:
            print(f"❌ JSON parsing failed: {str(e)}")
            print(f"🔍 Raw response: {analysis_content[:500]}...")
            
            # Fallback to pattern matching
            return self._parse_llm_analysis(analysis_content, build_info)
    
    def _parse_llm_analysis(self, analysis_content: str, build_info: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM analysis into structured format"""
        
        # Extract key information using pattern matching
        analysis_lower = analysis_content.lower()
        
        # Determine root cause category
        root_cause = "Unknown"
        if any(keyword in analysis_lower for keyword in ["test failure", "test failed", "tests failed"]):
            root_cause = "Test Failure"
        elif any(keyword in analysis_lower for keyword in ["compilation error", "build error", "compile failed"]):
            root_cause = "Compilation Error"
        elif any(keyword in analysis_lower for keyword in ["dependency", "package", "maven", "gradle"]):
            root_cause = "Dependency Issue"
        elif any(keyword in analysis_lower for keyword in ["credential", "authentication", "permission"]):
            root_cause = "Authentication/Credential Issue"
        elif any(keyword in analysis_lower for keyword in ["timeout", "timed out"]):
            root_cause = "Timeout Issue"
        elif any(keyword in analysis_lower for keyword in ["infrastructure", "network", "connection"]):
            root_cause = "Infrastructure Issue"
        elif any(keyword in analysis_lower for keyword in ["memory", "oom", "out of memory"]):
            root_cause = "Memory Issue"
        
        # Extract specific error messages (look for common patterns)
        error_patterns = [
            r'error[:\s]+([^\n]+)',
            r'failed[:\s]+([^\n]+)',
            r'exception[:\s]+([^\n]+)',
            r'fatal[:\s]+([^\n]+)'
        ]
        
        error_details = []
        for pattern in error_patterns:
            matches = re.findall(pattern, analysis_content, re.IGNORECASE)
            error_details.extend(matches[:2])  # Take first 2 matches per pattern
        
        # Extract recommendations (look for numbered lists or bullet points)
        recommendation_patterns = [
            r'\d+\.\s*([^\n]+)',
            r'[-*]\s*([^\n]+)',
            r'recommend[^:]*:\s*([^\n]+)',
            r'next steps[^:]*:\s*([^\n]+)'
        ]
        
        recommendations = []
        for pattern in recommendation_patterns:
            matches = re.findall(pattern, analysis_content, re.IGNORECASE)
            recommendations.extend(matches[:3])  # Take first 3 matches per pattern
        
        # Determine confidence based on analysis quality
        confidence = "medium"
        if len(error_details) > 0 and len(recommendations) > 0:
            confidence = "high"
        elif len(error_details) == 0 and len(recommendations) == 0:
            confidence = "low"
        
        return {
            "root_cause": root_cause,
            "error_details": error_details[:5] if error_details else ["No specific error details extracted"],
            "recommendations": recommendations[:5] if recommendations else ["Review build logs manually"],
            "build_status": build_info.get('result', 'UNKNOWN'),
            "analysis_confidence": confidence,
            "full_analysis": analysis_content,
            "build_duration": build_info.get('duration', 0),
            "build_timestamp": build_info.get('timestamp', 0),
            "failure_type": "build_failure" if build_info.get('result') != 'SUCCESS' else "success"
        }
    
    def _build_detailed_analysis(self, build_info: Dict[str, Any], analysis: Dict[str, Any], parsed_info: Dict[str, str]) -> str:
        """Build comprehensive Jenkins build analysis with detailed formatting"""
        
        # Extract build details
        build_status = build_info.get('result', 'UNKNOWN')
        build_duration = build_info.get('duration', 0)
        build_timestamp = build_info.get('timestamp', 0)
        build_url = build_info.get('url', 'Unknown')
        
        # Convert timestamp to readable format
        import datetime
        if build_timestamp:
            build_time = datetime.datetime.fromtimestamp(build_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            build_time = "Unknown"
        
        # Convert duration to readable format
        if build_duration:
            duration_seconds = build_duration / 1000
            duration_str = f"{duration_seconds:.1f} seconds"
        else:
            duration_str = "Unknown"
        
        # Determine status icon and color
        if build_status == 'SUCCESS':
            status_icon = "✅"
            status_text = "Success"
        elif build_status == 'FAILURE':
            status_icon = "❌"
            status_text = "Failed"
        elif build_status == 'UNSTABLE':
            status_icon = "⚠️"
            status_text = "Unstable"
        elif build_status == 'ABORTED':
            status_icon = "⏹️"
            status_text = "Aborted"
        else:
            status_icon = "❓"
            status_text = "Unknown"
        
        # Build detailed analysis text
        analysis_text = f"""### Jenkins Build Analysis for Build #{parsed_info['build_number']}

#### **1. Build Information**
- **Status:** {status_icon} {status_text}
- **Environment:** {parsed_info['env'].title()}
- **Job Path:** `{parsed_info['job_path']}`
- **Build Number:** {parsed_info['build_number']}
- **Duration:** {duration_str}
- **Timestamp:** {build_time}
- **Build URL:** [View Build]({build_url})

#### **2. Root Cause Analysis**
- **Root Cause:** {analysis.get('root_cause', 'Unknown')}
- **Failure Type:** {analysis.get('failure_type', 'Unknown')}
- **Analysis Confidence:** {analysis.get('analysis_confidence', 'Unknown')}

#### **3. Error Details**
{self._format_error_details(analysis.get('error_details', []))}

#### **4. Recommendations**
{self._format_recommendations(analysis.get('recommendations', []))}

#### **5. Full Analysis**
{analysis.get('full_analysis', 'No detailed analysis available')}

---

### **Build Health Summary**
- **Build Status:** {status_icon} {status_text}
- **Root Cause:** {analysis.get('root_cause', 'Unknown')}
- **Action Required:** {'Yes' if build_status != 'SUCCESS' else 'No'}

{self._get_build_summary(build_status, analysis.get('root_cause', 'Unknown'))}"""
        
        return analysis_text
    
    def _format_error_details(self, error_details: List[str]) -> str:
        """Format error details for display"""
        if not error_details or error_details == ["No specific error details extracted"]:
            return "- **Error Details:** No specific error details found in logs."
        
        formatted_errors = "- **Error Details:**\n"
        for i, error in enumerate(error_details[:5], 1):
            formatted_errors += f"  - **Error {i}:** {error}\n"
        
        if len(error_details) > 5:
            formatted_errors += f"  - ... and {len(error_details) - 5} more errors\n"
        
        return formatted_errors
    
    def _format_recommendations(self, recommendations: List[str]) -> str:
        """Format recommendations for display"""
        if not recommendations or recommendations == ["Review build logs manually"]:
            return "- **Recommendations:** No specific recommendations available."
        
        formatted_recs = "- **Recommendations:**\n"
        for i, rec in enumerate(recommendations[:5], 1):
            formatted_recs += f"  - **{i}.** {rec}\n"
        
        if len(recommendations) > 5:
            formatted_recs += f"  - ... and {len(recommendations) - 5} more recommendations\n"
        
        return formatted_recs
    
    def _get_build_summary(self, build_status: str, root_cause: str) -> str:
        """Get build health summary"""
        if build_status == 'SUCCESS':
            return "The build completed successfully with no issues."
        elif build_status == 'FAILURE':
            return f"Build failed due to: {root_cause}. Review the error details and recommendations above."
        elif build_status == 'UNSTABLE':
            return f"Build is unstable due to: {root_cause}. Some tests may have failed but build completed."
        elif build_status == 'ABORTED':
            return "Build was aborted. Check for manual intervention or timeout issues."
        else:
            return "Build status is unknown. Review logs for more information."
    
    async def _get_rag_solution(self, problem_identified: str, root_cause: str, user_query: str) -> Dict[str, Any]:
        """Get RAG solution based on problem and root cause analysis"""
        if not self.rag_service:
            return {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": "RAG service not available"
            }
        
        try:
            # Get intelligent RAG solution
            rag_result = await self.rag_service.get_intelligent_rag_solution(
                problem_identified, 
                root_cause, 
                user_query
            )
            
            return rag_result
            
        except Exception as e:
            print(f"❌ RAG solution error: {str(e)}")
            return {
                "rag_solution": None,
                "similarity_score": 0.0,
                "jira_id": None,
                "message": f"RAG error: {str(e)}"
            }
