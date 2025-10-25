"""
GitHub Agent - Modular version based on github.py
Handles GitHub PR analysis, CI/CD checks, and code reviews
"""

import asyncio
import aiohttp
import re
from typing import Dict, Any, List, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import AzureChatOpenAI

from ..config.settings import Settings
from ..utils.logging import ToolCallLogger
from ..utils.confidence_detector import ConfidenceDetector
from langchain_core.prompts import ChatPromptTemplate
import json
from ..prompts.github import GITHUB_SYSTEM_PROMPT, get_github_analysis_prompt

class GitHubAgent:
    """GitHub PR analysis and CI/CD debugging agent"""
    
    def __init__(self, llm: AzureChatOpenAI, tool_logger: ToolCallLogger, rag_service=None):
        self.llm = llm
        self.tool_logger = tool_logger
        self.rag_service = rag_service
        self.github_tools = []
        self.initialized = False
    
    async def initialize(self) -> bool:
        """Initialize GitHub MCP tools"""
        try:
            print("🔄 Loading GitHub MCP tools...")
            
            # Load GitHub MCP tools
            client = MultiServerMCPClient({
                "github": {
                    "url": "https://api.githubcopilot.com/mcp/",
                    "transport": "streamable_http",
                    "headers": {
                        "Authorization": f"Bearer {Settings.GITHUB_TOKEN}",
                    }
                }
            })
            print("Settings.GITHUB_TOKEN")
            print(Settings.GITHUB_TOKEN)
            
            tools = await client.get_tools()
            
            # Find the specific tools we need
            target_tool_names = [
                "get_pull_request_status",      # For CI/CD checks
                "get_pull_request_comments",    # For review comments
                "get_pull_request_reviews",     # For overall reviews
                "get_pull_request",             # For basic PR info
                "list_workflow_runs",           # For CI workflow details
                "get_workflow_run",             # For specific workflow info
                "list_workflow_jobs",    
                "get_issue_comments"            # For job details
            ]
            
            self.github_tools = []
            for tool in tools:
                if tool.name in target_tool_names:
                    self.github_tools.append(tool)
                    print(f"✅ Found: {tool.name}")
            
            print(f"✅ GitHub tools loaded: {len(self.github_tools)}")
            self.initialized = True
            return True
                
        except Exception as e:
            print(f"❌ Failed to initialize GitHub tools: {str(e)}")
            self.github_tools = []
            return False
    
    async def analyze(self, user_prompt: str) -> Dict[str, Any]:
        """Main analysis method for GitHub issues"""
        
        if not self.initialized:
            await self.initialize()
        
        print("🔧 GitHub Agent: Starting intelligent GitHub analysis...")
        
        try:
            # Extract GitHub URL from user prompt
            github_url = self._extract_github_url(user_prompt)
            
            if not github_url:
                return {
                    "status": "failed",
                    "error": "Could not extract GitHub URL from request",
                    "suggestions": [
                        "Provide a GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)",
                        "Include the full GitHub PR URL in your request"
                    ]
                }
            
            print(f"🔧 Detected GitHub URL: {github_url}")
            
            # Parse GitHub URL
            parsed_info = self._parse_github_url(github_url)
            if not parsed_info:
                return {
                    "status": "failed",
                    "error": "Invalid GitHub URL format",
                    "suggestions": ["Provide a valid GitHub PR URL"]
                }
            
            print(f"🔧 Owner: {parsed_info['owner']}")
            print(f"🔧 Repo: {parsed_info['repo']}")
            print(f"🔧 PR Number: {parsed_info['pr_number']}")
            
            # Get comprehensive PR info
            pr_data = await self._get_all_pr_info(
                parsed_info['owner'], 
                parsed_info['repo'], 
                parsed_info['pr_number']
            )
            
            if not pr_data:
                return {
                    "status": "failed",
                    "error": "Failed to fetch GitHub PR information",
                    "suggestions": ["Check GitHub URL accessibility", "Verify PR exists"]
                }
            
            # Check for health check failures that should route to K8s agent
            health_check_info = self._detect_health_check_failures(pr_data)
            if health_check_info:
                print(f"🔧 Health check failures detected: {health_check_info}")
                return {
                    "status": "route_to_k8s",
                    "health_check_info": health_check_info,
                    "message": "Health check failures detected, routing to Kubernetes agent for analysis"
                }
            
            # Check for Jenkins build failures that should route to Jenkins agent
            jenkins_failure_info = self._detect_jenkins_build_failures(pr_data)
            if jenkins_failure_info:
                print(f"🔧 Jenkins build failures detected: {jenkins_failure_info}")
                return {
                    "status": "route_to_jenkins",
                    "jenkins_failure_info": jenkins_failure_info,
                    "message": "Jenkins build failures detected, routing to Jenkins agent for analysis"
                }
            
            # Analyze the PR with LLM
            analysis = await self._analyze_pr_with_llm(pr_data, user_prompt)
            
            # Get RAG solution based on problem and root cause
            rag_solution = await self._get_rag_solution(
                analysis.get("problem_identified", ""),
                analysis.get("root_cause", ""),
                user_prompt
            )
            
            # Get confidence information
            confidence_info = ConfidenceDetector.detect_confidence(user_prompt)
            
            # Force return only the standardized format with RAG solution
            return {
                "status": "success",
                "problem_identified": analysis.get("problem_identified", "Unknown problem"),
                "root_cause": analysis.get("root_cause", "Unknown root cause"),
                "solution": analysis.get("solution", "No solution provided"),
                "summary": analysis.get("summary", "No summary available"),
                "rag_solution": rag_solution,
                "confidence": confidence_info["confidence"],
                "confidence_level": confidence_info["confidence_level"],
                "confidence_reasoning": confidence_info["reasoning"]
            }
            
        except Exception as e:
            print(f"❌ GitHub Agent error: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "suggestions": ["Check GitHub connectivity", "Verify PR URL"]
            }
    
    def _detect_health_check_failures(self, pr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect health check failures in PR comments that should route to K8s agent"""
        try:
            # Get all comments from the PR
            api_issue_comments = pr_data.get("api_issue_comments", []) or []
            mcp_comments = pr_data.get("mcp_comments", []) or []
            all_comments = api_issue_comments + mcp_comments
            
            # Look for health check failure patterns
            health_check_patterns = [
                r"Health check did not complete successfully for the following env: (\w+)",
                r"Health check failed for applications: \[([^\]]+)\]",
                r"argo app sync is in failed state",
                r"values_properties file not found",
                r"GetValuesPropertiesFileActivity",
                r"GetArgoAppSyncStatusActivity"
            ]
            
            detected_failures = []
            environment = None
            applications = []
            
            for comment in all_comments:
                comment_body = comment.get("body", "")
                comment_lower = comment_body.lower()
                
                # Check for health check failure patterns
                for pattern in health_check_patterns:
                    matches = re.findall(pattern, comment_body, re.IGNORECASE)
                    if matches:
                        detected_failures.append({
                            "pattern": pattern,
                            "matches": matches,
                            "comment_body": comment_body[:200] + "..." if len(comment_body) > 200 else comment_body
                        })
                
                # Extract environment
                env_match = re.search(r"env: (\w+)", comment_body, re.IGNORECASE)
                if env_match:
                    environment = env_match.group(1).lower()
                
                # Extract applications
                app_match = re.search(r"applications: \[([^\]]+)\]", comment_body, re.IGNORECASE)
                if app_match:
                    apps_str = app_match.group(1)
                    applications = [app.strip().strip('"\'') for app in apps_str.split(',')]
            
            # If we found health check failures, return the info for K8s routing
            if detected_failures and environment and applications:
                return {
                    "environment": environment,
                    "applications": applications,
                    "failures": detected_failures,
                    "namespace_pattern": f"{environment}-{applications[0]}" if applications else None
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Health check detection error: {str(e)}")
            return None

    def _detect_jenkins_build_failures(self, pr_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect Jenkins build failures in PR comments that should route to Jenkins agent"""
        try:
            # Get all comments from the PR
            api_issue_comments = pr_data.get("api_issue_comments", []) or []
            mcp_comments = pr_data.get("mcp_comments", []) or []
            all_comments = api_issue_comments + mcp_comments
            
            # Look for Jenkins build failure patterns
            jenkins_failure_patterns = [
                r"WaitForJenkinsJobCompletionActivity: jenkins build failed, checked \d+ times, URL: (https://jenkins-[^/]+/[^\s]+)",
                r"jenkins build failed, checked \d+ times, URL: (https://jenkins-[^/]+/[^\s]+)",
                r"CI Workflow did not complete successfully.*URL: (https://jenkins-[^/]+/[^\s]+)",
                r"jenkins.*failed.*URL: (https://jenkins-[^/]+/[^\s]+)",
                r"build failed.*URL: (https://jenkins-[^/]+/[^\s]+)"
            ]
            
            # General Jenkins URL pattern for any Jenkins URL in comments
            general_jenkins_url_pattern = r"(https://jenkins-[^/\s]+/[^\s]+)"
            
            detected_failures = []
            jenkins_urls = []
            
            for comment in all_comments:
                comment_body = comment.get("body", "")
                comment_lower = comment_body.lower()
                
                # Check for Jenkins build failure patterns
                for pattern in jenkins_failure_patterns:
                    matches = re.findall(pattern, comment_body, re.IGNORECASE)
                    if matches:
                        for match in matches:
                            jenkins_url = match.strip()
                            if jenkins_url:
                                jenkins_urls.append(jenkins_url)
                                detected_failures.append({
                                    "pattern": pattern,
                                    "jenkins_url": jenkins_url,
                                    "comment_body": comment_body[:200] + "..." if len(comment_body) > 200 else comment_body
                                })
                
                # Also look for general Jenkins failure indicators
                if any(keyword in comment_lower for keyword in [
                    "jenkins build failed", 
                    "ci workflow did not complete successfully",
                    "waitforjenkinsjobcompletionactivity",
                    "jenkins.*failed"
                ]):
                    # Try to extract Jenkins URL from the comment
                    url_match = re.search(r'https://jenkins-[^/\s]+/[^\s]+', comment_body)
                    if url_match:
                        jenkins_url = url_match.group(0)
                        jenkins_urls.append(jenkins_url)
                        detected_failures.append({
                            "pattern": "general_jenkins_failure",
                            "jenkins_url": jenkins_url,
                            "comment_body": comment_body[:200] + "..." if len(comment_body) > 200 else comment_body
                        })
                
                # NEW: Check for ANY Jenkins URL in comments (not just failure patterns)
                general_jenkins_matches = re.findall(general_jenkins_url_pattern, comment_body)
                if general_jenkins_matches:
                    for jenkins_url in general_jenkins_matches:
                        jenkins_url = jenkins_url.strip()
                        if jenkins_url and jenkins_url not in jenkins_urls:  # Avoid duplicates
                            jenkins_urls.append(jenkins_url)
                            detected_failures.append({
                                "pattern": "general_jenkins_url",
                                "jenkins_url": jenkins_url,
                                "comment_body": comment_body[:200] + "..." if len(comment_body) > 200 else comment_body
                            })
                            print(f"🔧 Found general Jenkins URL in comment: {jenkins_url}")
            
            # If we found Jenkins build failures, return the info for Jenkins routing
            if detected_failures and jenkins_urls:
                # Ensure all Jenkins URLs have /console suffix for proper Jenkins agent analysis
                console_urls = []
                for url in jenkins_urls:
                    if not url.endswith('/console'):
                        console_url = url.rstrip('/') + '/console'
                        console_urls.append(console_url)
                        print(f"🔧 Added /console suffix to Jenkins URL: {console_url}")
                    else:
                        console_urls.append(url)
                
                return {
                    "jenkins_urls": console_urls,
                    "failures": detected_failures,
                    "failure_type": "jenkins_build_failure"
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Jenkins build failure detection error: {str(e)}")
            return None

    def _extract_github_url(self, user_prompt: str) -> Optional[str]:
        """Extract GitHub URL from user prompt"""
        # Pattern to match GitHub URLs
        github_pattern = r'https://github\.com/[^\s/]+/[^\s/]+/pull/\d+'
        match = re.search(github_pattern, user_prompt)
        return match.group(0) if match else None
    
    def _parse_github_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Extract owner, repo, and PR number from GitHub URL
        Example: https://github.com/Meesho/search-orchestrator/pull/2006
        """
        match = re.search(r'github\.com/([^/]+)/([^/]+)/pull/(\d+)', url)
        if not match:
            return None
        
        return {
            "owner": match.group(1),
            "repo": match.group(2),
            "pr_number": int(match.group(3))
        }
    
    async def _get_all_pr_info(self, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive PR info using both MCP and direct API"""
        
        results = {
            "basic_info": None,
            "ci_status": None,
            "mcp_comments": None,
            "mcp_reviews": None,
            "api_issue_comments": None,
            "workflows": None
        }
        
        # 1. MCP: Basic PR info
        pr_tool = next((t for t in self.github_tools if t.name == "get_pull_request"), None)
        if pr_tool:
            try:
                pr_result = await pr_tool.ainvoke({
                    "owner": owner, "repo": repo, "pullNumber": pr_number
                })
                # Handle both string and dict responses
                if isinstance(pr_result, str):
                    import json
                    try:
                        results["basic_info"] = json.loads(pr_result)
                    except:
                        results["basic_info"] = {"raw_response": pr_result}
                else:
                    results["basic_info"] = pr_result
            except Exception as e:
                print(f"❌ MCP PR info failed: {str(e)}")
        
        # 2. MCP: CI Status
        status_tool = next((t for t in self.github_tools if t.name == "get_pull_request_status"), None)
        if status_tool:
            try:
                status_result = await status_tool.ainvoke({
                    "owner": owner, "repo": repo, "pullNumber": pr_number
                })
                # Handle both string and dict responses
                if isinstance(status_result, str):
                    import json
                    try:
                        results["ci_status"] = json.loads(status_result)
                    except:
                        results["ci_status"] = {"raw_response": status_result}
                else:
                    results["ci_status"] = status_result
            except Exception as e:
                print(f"❌ MCP CI status failed: {str(e)}")
        
        # 3. MCP: Review comments (code-specific)
        comments_tool = next((t for t in self.github_tools if t.name == "get_pull_request_comments"), None)
        if comments_tool:
            try:
                comments_result = await comments_tool.ainvoke({
                    "owner": owner, "repo": repo, "pullNumber": pr_number
                })
                # Handle both string and dict responses
                if isinstance(comments_result, str):
                    import json
                    try:
                        results["mcp_comments"] = json.loads(comments_result)
                    except:
                        results["mcp_comments"] = []
                else:
                    results["mcp_comments"] = comments_result
            except Exception as e:
                print(f"❌ MCP comments failed: {str(e)}")
        
        # 4. MCP: Reviews
        reviews_tool = next((t for t in self.github_tools if t.name == "get_pull_request_reviews"), None)
        if reviews_tool:
            try:
                reviews_result = await reviews_tool.ainvoke({
                    "owner": owner, "repo": repo, "pullNumber": pr_number
                })
                # Handle both string and dict responses
                if isinstance(reviews_result, str):
                    import json
                    try:
                        results["mcp_reviews"] = json.loads(reviews_result)
                    except:
                        results["mcp_reviews"] = []
                else:
                    results["mcp_reviews"] = reviews_result
            except Exception as e:
                print(f"❌ MCP reviews failed: {str(e)}")
        
        # 5. DIRECT API: Issue comments (the ones we saw!)
        try:
            headers = {
                "Authorization": f"token {Settings.GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            async with aiohttp.ClientSession() as session:
                # Get issue comments (general PR comments)
                url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        all_comments = await response.json()
                        print(f"🔍 All comments: {all_comments}")
                        turbo_turtle_comments = [
                            comment for comment in all_comments 
                            if comment.get("user", {}).get("login") in ["turbo-turtle-github[bot]"]
                        ]
                        print(f"🔍 Turbo turtle comments: {turbo_turtle_comments}")
                        results["api_issue_comments"] = await response.json()
                    else:
                        print(f"❌ API issue comments failed: {response.status}")
        except Exception as e:
            print(f"❌ API issue comments error: {str(e)}")
        
        return results
    
    async def _analyze_pr_with_llm(self, pr_data: Dict[str, Any], user_prompt: str) -> Dict[str, Any]:
        """
        Generate comprehensive PR analysis using standardized format
        """
        try:
            # Extract basic PR info
            basic_info = pr_data.get("basic_info", {})
            ci_status = pr_data.get("ci_status", {})
            mcp_comments = pr_data.get("mcp_comments", [])
            mcp_reviews = pr_data.get("mcp_reviews", [])
            api_issue_comments = pr_data.get("api_issue_comments", [])
            turbo_turtle_comments = []
            if api_issue_comments:
                turbo_turtle_comments = [
                    comment for comment in api_issue_comments 
                    if comment.get("user", {}).get("login") in ["turbo-turtle-github[bot]"]
                ]
            print(f"🔍 Turbo turtle comments: {turbo_turtle_comments}")
            # Use the new standardized prompt format
            
            # Prepare data for the prompt
            pr_data_for_prompt = {
                'owner': 'Unknown',
                'repo': 'Unknown', 
                'pr_number': 'Unknown',
                'pr_url': 'Unknown',
                'basic_info': str(basic_info),
                'ci_status': str(ci_status),
                'review_comments': str(mcp_comments),
                'reviews': str(mcp_reviews),
                'issue_comments': str(turbo_turtle_comments)
            }
            
            prompt = get_github_analysis_prompt(pr_data_for_prompt)

            response = await self.llm.ainvoke([{
                "role": "system", 
                "content": GITHUB_SYSTEM_PROMPT
            }, {
                "role": "user", 
                "content": prompt
            }])

            analysis_content = response.content
            
            # Parse the JSON response into structured format
            structured_analysis = self._parse_json_analysis(analysis_content, pr_data)
            
            return structured_analysis

        except Exception as e:
            print(f"❌ Analysis failed: {str(e)}")
            return {
                "problem_identified": "Analysis failed",
                "root_cause": str(e),
                "solution": ["Retry analysis", "Check configuration"],
                "summary": "Unable to analyze PR due to technical error"
            }
    
    def _parse_json_analysis(self, analysis_content: str, pr_data: Dict[str, Any]) -> Dict[str, Any]:
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
            return self._parse_llm_analysis(analysis_content, pr_data)
    
    def _build_detailed_analysis(self, basic_info: Dict, ci_status: Dict, mcp_comments: List, mcp_reviews: List, api_issue_comments: List) -> Dict[str, Any]:
        """Build comprehensive PR analysis with detailed formatting"""
        
        # Extract PR details
        pr_title = basic_info.get("title", "Unknown")
        pr_state = basic_info.get("state", "Unknown")
        pr_author = basic_info.get("user", {}).get("login", "Unknown")
        pr_merged_by = basic_info.get("merged_by", {}).get("login", "Unknown") if basic_info.get("merged_by") else "Not merged"
        pr_labels = [label.get("name", "") for label in basic_info.get("labels", [])]
        pr_commits = basic_info.get("commits", 0)
        pr_additions = basic_info.get("additions", 0)
        pr_deletions = basic_info.get("deletions", 0)
        pr_files_changed = basic_info.get("changed_files", 0)
        
        # Analyze CI/CD status
        ci_analysis = self._analyze_ci_status(ci_status)
        
        # Analyze code review comments
        review_analysis = self._analyze_review_comments(mcp_comments)
        
        # Analyze reviews
        reviews_analysis = self._analyze_reviews(mcp_reviews)
        
        # Analyze issue comments
        issue_comments_analysis = self._analyze_issue_comments(api_issue_comments)
        
        # Determine overall PR health
        pr_health = self._determine_pr_health(ci_analysis, review_analysis, reviews_analysis)
        
        # Build detailed analysis text
        analysis_text = f"""### Pull Request Analysis for PR #{basic_info.get('number', 'Unknown')}
            #### **1. CI/CD Check Status**
            {ci_analysis['status_text']}

            #### **2. Code Review Comments**
            {review_analysis['summary_text']}

            #### **3. Reviews**
            {reviews_analysis['summary_text']}

            #### **4. Basic PR Information**
            - **Title:** `{pr_title}`
            - **State:** {pr_state.title()}
            - **Created By:** [{pr_author}](https://github.com/{pr_author})
            - **Merged By:** {f"[{pr_merged_by}](https://github.com/{pr_merged_by})" if pr_merged_by != "Not merged" else "Not merged"}
            - **Labels:** {', '.join(pr_labels) if pr_labels else 'None'}
            - **Commits:** {pr_commits}
            - **Files Changed:** {pr_files_changed}
            - **Additions:** {pr_additions} lines
            - **Deletions:** {pr_deletions} lines

            #### **5. Issue Comments**
            {issue_comments_analysis['summary_text']}

            ---

            ### **Overall PR Health**
            - **CI/CD Status:** {ci_analysis['status_icon']} {ci_analysis['status']}.
            - **Code Review Feedback:** {review_analysis['status_icon']} {review_analysis['status']}.
            - **Approval Status:** {reviews_analysis['status_icon']} {reviews_analysis['status']}.
            - **Merge Status:** {'✅ Successfully merged' if pr_state == 'closed' and pr_merged_by != "Not merged" else '❌ Not merged' if pr_state == 'closed' else '⏳ Open'}.

            {pr_health['summary']}"""
        
        return {
                "pr_health": pr_health['status'],
                "ci_status": ci_analysis['status'],
                "analysis_text": analysis_text,
                "detailed_analysis": {
                    "ci_cd": ci_analysis,
                    "code_review": review_analysis,
                    "reviews": reviews_analysis,
                    "issue_comments": issue_comments_analysis,
                    "basic_info": {
                        "title": pr_title,
                        "state": pr_state,
                        "author": pr_author,
                        "merged_by": pr_merged_by,
                        "labels": pr_labels,
                        "commits": pr_commits,
                        "additions": pr_additions,
                        "deletions": pr_deletions,
                        "files_changed": pr_files_changed
                    }
                },
                "issues": pr_health['issues'],
                "recommendations": pr_health['recommendations'],
                "analysis_confidence": pr_health['confidence']
            }
        
    def _analyze_ci_status(self, ci_status: Dict) -> Dict[str, Any]:
        """Analyze CI/CD status"""
        if not ci_status or not isinstance(ci_status, dict):
            return {
                "status": "Unknown",
                "status_icon": "❓",
                "status_text": "- **Build Status:** CI/CD status not available.\n- **Details:** Unable to fetch build information.",
                "has_failures": False
            }
        
        # Check if there are any failing checks
        checks = ci_status.get("check_runs", [])
        statuses = ci_status.get("statuses", [])
        
        all_checks = checks + statuses
        failing_checks = [check for check in all_checks if check.get("conclusion") == "failure" or check.get("state") == "failure"]
        passing_checks = [check for check in all_checks if check.get("conclusion") == "success" or check.get("state") == "success"]
        pending_checks = [check for check in all_checks if check.get("conclusion") == "pending" or check.get("state") == "pending"]
        
        # Also check the overall state
        overall_state = ci_status.get("state", "").lower()
        if overall_state == "failure":
            failing_checks = all_checks  # All checks failed
        elif overall_state == "success":
            passing_checks = all_checks  # All checks passed
        elif overall_state == "pending":
            pending_checks = all_checks  # All checks pending
        
        if failing_checks:
            status = "Failing"
            status_icon = "❌"
            status_text = f"- **Build Status:** {len(failing_checks)} check(s) failed.\n- **Details:** "
            for i, check in enumerate(failing_checks[:3], 1):
                check_name = check.get("name", f"Check {i}")
                status_text += f"\n  - {check_name}: Failed"
            if len(failing_checks) > 3:
                status_text += f"\n  - ... and {len(failing_checks) - 3} more failures"
        elif pending_checks:
            status = "Pending"
            status_icon = "⏳"
            status_text = f"- **Build Status:** {len(pending_checks)} check(s) pending.\n- **Details:** Checks are still running."
        elif passing_checks:
            status = "Passing"
            status_icon = "✅"
            status_text = f"- **Build Status:** All CI/CD checks have passed successfully.\n- **Details:** {len(passing_checks)} successful check(s), including:"
            for i, check in enumerate(passing_checks[:5], 1):
                check_name = check.get("name", f"Check {i}")
                status_text += f"\n  - {check_name}"
            if len(passing_checks) > 5:
                status_text += f"\n  - ... and {len(passing_checks) - 5} more"
        else:
            status = "Unknown"
            status_icon = "❓"
            status_text = "- **Build Status:** No check information available.\n- **Details:** Unable to determine build status."
        
        return {
            "status": status,
            "status_icon": status_icon,
            "status_text": status_text,
            "has_failures": len(failing_checks) > 0,
            "failing_checks": failing_checks,
            "passing_checks": passing_checks,
            "pending_checks": pending_checks
        }
    
    def _analyze_review_comments(self, mcp_comments: List) -> Dict[str, Any]:
        """Analyze code review comments"""
        if not mcp_comments or not isinstance(mcp_comments, list):
            return {
                "status": "No code review comments",
                "status_icon": "📋",
                "summary_text": "- **Total Comments:** 0\n- **Highlights:** No code review comments found.",
                "comments": []
            }
        
        comments_text = f"- **Total Comments:** {len(mcp_comments)}\n- **Highlights:**"
        
        for i, comment in enumerate(mcp_comments[:5], 1):
            author = comment.get("user", {}).get("login", "Unknown")
            body = comment.get("body", "")[:100]
            comments_text += f"\n  - **Comment {i}:** \"{body}...\" - {author}"
        
        if len(mcp_comments) > 5:
            comments_text += f"\n  - ... and {len(mcp_comments) - 5} more comments"
        
        return {
            "status": f"{len(mcp_comments)} code review comment(s)",
            "status_icon": "💬",
            "summary_text": comments_text,
            "comments": mcp_comments
        }
    
    def _analyze_reviews(self, mcp_reviews: List) -> Dict[str, Any]:
        """Analyze PR reviews"""
        if not mcp_reviews or not isinstance(mcp_reviews, list):
            return {
                "status": "No reviews",
                "status_icon": "📋",
                "summary_text": "- **Total Reviews:** 0\n- **Highlights:** No reviews found.",
                "reviews": []
            }
        
        approved_reviews = [r for r in mcp_reviews if r.get("state") == "APPROVED"]
        commented_reviews = [r for r in mcp_reviews if r.get("state") == "COMMENTED"]
        changes_requested = [r for r in mcp_reviews if r.get("state") == "CHANGES_REQUESTED"]
        
        reviews_text = f"- **Total Reviews:** {len(mcp_reviews)}"
        
        if approved_reviews:
            reviewers = [r.get("user", {}).get("login", "Unknown") for r in approved_reviews]
            reviews_text += f"\n  - **{len(approved_reviews)} Approval(s):** The PR has been approved by:"
            for reviewer in reviewers:
                reviews_text += f"\n    - Reviewer: `{reviewer}`"
        
        if commented_reviews:
            reviews_text += f"\n  - **{len(commented_reviews)} Commented Review(s):** General feedback on the code."
        
        if changes_requested:
            reviews_text += f"\n  - **{len(changes_requested)} Change Request(s):** Changes requested by reviewers."
        
        status = f"{len(approved_reviews)} approval(s), {len(commented_reviews)} comment(s), {len(changes_requested)} change request(s)"
        status_icon = "✅" if approved_reviews else "💬" if commented_reviews else "❌" if changes_requested else "📋"
        
        return {
            "status": status,
            "status_icon": status_icon,
            "summary_text": reviews_text,
            "reviews": mcp_reviews,
            "approved": approved_reviews,
            "commented": commented_reviews,
            "changes_requested": changes_requested
        }
    
    def _analyze_issue_comments(self, api_issue_comments: List) -> Dict[str, Any]:
        """Analyze issue comments (general PR comments)"""
        if not api_issue_comments or not isinstance(api_issue_comments, list):
            return {
                "status": "No issue comments",
                "status_icon": "📋",
                "summary_text": "- **General Comments:** No general issue comments found.",
                "comments": []
            }
        
        comments_text = f"- **General Comments:** The issue comments primarily consist of:"
        
        # Categorize comments
        bot_comments = [c for c in api_issue_comments if c.get("user", {}).get("type") == "Bot"]
        user_comments = [c for c in api_issue_comments if c.get("user", {}).get("type") == "User"]
        
        if bot_comments:
            comments_text += f"\n  - {len(bot_comments)} bot notification(s) regarding CI/CD status and workflow updates"
        
        if user_comments:
            comments_text += f"\n  - {len(user_comments)} user comment(s) with feedback and discussions"
        
        # Show sample comments
        for i, comment in enumerate(api_issue_comments[:3], 1):
            author = comment.get("user", {}).get("login", "Unknown")
            body = comment.get("body", "")[:80]
            comment_type = "Bot" if comment.get("user", {}).get("type") == "Bot" else "User"
            comments_text += f"\n  - **Comment {i}:** ({comment_type}) {author}: {body}..."
        
        if len(api_issue_comments) > 3:
            comments_text += f"\n  - ... and {len(api_issue_comments) - 3} more comments"
        
        return {
            "status": f"{len(api_issue_comments)} issue comment(s)",
            "status_icon": "💬",
            "summary_text": comments_text,
            "comments": api_issue_comments,
            "bot_comments": bot_comments,
            "user_comments": user_comments
        }
    
    def _determine_pr_health(self, ci_analysis: Dict, review_analysis: Dict, reviews_analysis: Dict) -> Dict[str, Any]:
        """Determine overall PR health"""
        issues = []
        recommendations = []
        
        # Check CI status
        if ci_analysis["has_failures"]:
            issues.append("CI/CD checks are failing")
            recommendations.append("Fix failing CI/CD checks before merging")
        elif ci_analysis["status"] == "Pending":
            issues.append("CI/CD checks are still pending")
            recommendations.append("Wait for CI/CD checks to complete")
        
        # Check review status
        if reviews_analysis.get("changes_requested"):
            issues.append("Changes requested by reviewers")
            recommendations.append("Address reviewer feedback")
        elif not reviews_analysis.get("approved"):
            issues.append("No approvals yet")
            recommendations.append("Request reviews from team members")
        
        # Determine overall status
        if not issues:
            status = "Healthy"
            summary = "The PR appears to be in good health with no outstanding issues."
        elif len(issues) == 1:
            status = "Needs Attention"
            summary = f"The PR has one issue: {issues[0]}."
        else:
            status = "Has Issues"
            summary = f"The PR has {len(issues)} issues that need attention."
        
        return {
            "status": status,
            "issues": issues,
            "recommendations": recommendations,
            "summary": summary,
            "confidence": "high" if len(issues) == 0 else "medium"
        }
    
    def _parse_llm_analysis(self, analysis_content: str, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM analysis into structured format"""
        
        # Extract key information using pattern matching
        analysis_lower = analysis_content.lower()
        
        # Determine PR health
        pr_health = "Unknown"
        if any(keyword in analysis_lower for keyword in ["passing", "success", "healthy", "good"]):
            pr_health = "Passing"
        elif any(keyword in analysis_lower for keyword in ["failing", "failed", "error", "issue"]):
            pr_health = "Failing"
        elif any(keyword in analysis_lower for keyword in ["attention", "review", "needs"]):
            pr_health = "Needs Attention"
        
        # Determine CI status
        ci_status = "Unknown"
        if any(keyword in analysis_lower for keyword in ["ci passing", "checks passing", "build success"]):
            ci_status = "Passing"
        elif any(keyword in analysis_lower for keyword in ["ci failing", "checks failing", "build failed"]):
            ci_status = "Failing"
        
        # Extract issues and recommendations
        issue_patterns = [
            r'issue[:\s]+([^\n]+)',
            r'problem[:\s]+([^\n]+)',
            r'concern[:\s]+([^\n]+)',
            r'error[:\s]+([^\n]+)'
        ]
        
        issues = []
        for pattern in issue_patterns:
            matches = re.findall(pattern, analysis_content, re.IGNORECASE)
            issues.extend(matches[:3])  # Take first 3 matches per pattern
        
        recommendation_patterns = [
            r'recommend[^:]*:\s*([^\n]+)',
            r'suggestion[^:]*:\s*([^\n]+)',
            r'next steps[^:]*:\s*([^\n]+)',
            r'action[^:]*:\s*([^\n]+)'
        ]
        
        recommendations = []
        for pattern in recommendation_patterns:
            matches = re.findall(pattern, analysis_content, re.IGNORECASE)
            recommendations.extend(matches[:3])  # Take first 3 matches per pattern
        
        # Determine confidence based on analysis quality
        confidence = "medium"
        if len(issues) > 0 and len(recommendations) > 0:
            confidence = "high"
        elif len(issues) == 0 and len(recommendations) == 0:
            confidence = "low"
        
        return {
            "problem_identified": issues[0] if issues else "No specific issues identified",
            "root_cause": "Analysis based on pattern matching",
            "solution": recommendations[:5] if recommendations else ["Review PR manually"],
            "summary": f"PR health: {pr_health}, CI status: {ci_status}"
        }
    
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


    async def _intelligent_github_analysis_fixed(self, raw_analysis: str, user_prompt: str) -> Dict[str, Any]:
        """ENHANCED: Comprehensive GitHub analysis with all PR details like github.py"""
        
        # Initialize comprehensive findings structure
        findings = {
            "pr_metadata": {},
            "ci_cd_status": {},
            "failed_checks": [],
            "health_issues": [],
            "code_review_feedback": [],
            "issue_comments": [],
            "bot_notifications": [],
            "workflow_runs": [],
            "errors": [],
            "recommendations": [],
            "summary": "Comprehensive GitHub analysis completed"
        }
        
        try:
            # Enhanced structured LLM parsing with comprehensive analysis
            analysis_prompt = ChatPromptTemplate.from_template("""
            You are analyzing comprehensive GitHub DevOps data. Extract ALL structured findings from the raw analysis.

            USER REQUEST: {user_prompt}

            RAW GITHUB ANALYSIS:
            {raw_analysis}

            Based on the comprehensive analysis, extract ALL key information and respond with ONLY a valid JSON object (no markdown, no extra text):

            {{
                "pr_metadata": {{
                    "title": "PR title",
                    "author": "author_username", 
                    "state": "open/closed/merged",
                    "labels": ["label1", "label2"],
                    "commits": 0,
                    "additions": 0,
                    "deletions": 0,
                    "changed_files": 0,
                    "created_at": "timestamp",
                    "updated_at": "timestamp"
                }},
                "ci_cd_status": {{
                    "overall_status": "success/failure/pending",
                    "total_checks": 0,
                    "passed_checks": 0,
                    "failed_checks": 0,
                    "pending_checks": 0,
                    "workflow_status": "success/failure/pending"
                }},
                "failed_checks": [
                    {{"name": "check_name", "status": "failed", "details": "error_details", "severity": "high", "url": "check_url"}}
                ],
                "health_issues": [
                    {{"type": "ci_cd", "status": "failed", "details": "issue_details", "severity": "high"}}
                ],
                "code_review_feedback": [
                    {{"reviewer": "username", "state": "approved/changes_requested/commented", "body": "review_comment", "file": "file_path"}}
                ],
                "issue_comments": [
                    {{"author": "username", "body": "comment_text", "created_at": "timestamp", "type": "general"}}
                ],
                "bot_notifications": [
                    {{"bot": "bot_name", "message": "notification_text", "type": "ci_failure/success/status"}}
                ],
                "workflow_runs": [
                    {{"name": "workflow_name", "status": "success/failure", "conclusion": "success/failure/cancelled", "url": "workflow_url"}}
                ],
                "errors": [
                    {{"source": "jenkins", "error": "build_failure_details", "severity": "high"}}
                ],
                "recommendations": [
                    "Fix Jenkins build failure",
                    "Address code review feedback",
                    "Review Quality Gate settings"
                ],
                "summary": "Comprehensive summary of all findings"
            }}
            """)
            
            analysis_chain = analysis_prompt | self.llm
            
            response = await analysis_chain.ainvoke({
                "user_prompt": user_prompt,
                "raw_analysis": raw_analysis
            })
            
            # Clean the response content
            content = response.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            
            # Parse JSON
            parsed_findings = json.loads(content)
            findings.update(parsed_findings)
            
        except Exception as json_error:
            print(f"⚠️ JSON parsing failed, using enhanced regex extraction: {str(json_error)}")
            
            # ENHANCED FALLBACK: Use comprehensive regex extraction from raw analysis
            analysis_lower = raw_analysis.lower()
            
            # Extract PR metadata
            if "title:" in analysis_lower:
                findings["pr_metadata"]["title"] = "PR title extracted from analysis"
            if "author:" in analysis_lower:
                findings["pr_metadata"]["author"] = "Author extracted from analysis"
            if "state:" in analysis_lower:
                findings["pr_metadata"]["state"] = "State extracted from analysis"
            
            # Extract CI/CD status
            if "ci" in analysis_lower and ("pass" in analysis_lower or "success" in analysis_lower):
                findings["ci_cd_status"]["overall_status"] = "success"
            elif "ci" in analysis_lower and ("fail" in analysis_lower or "error" in analysis_lower):
                findings["ci_cd_status"]["overall_status"] = "failure"
            else:
                findings["ci_cd_status"]["overall_status"] = "pending"
            
            # Extract failed checks
            if "jenkins build failed" in analysis_lower or "quality gate" in analysis_lower:
                findings["failed_checks"].append({
                    "name": "Jenkins CI/CD Pipeline",
                    "status": "failed", 
                    "details": "Jenkins build failed - check build logs for details",
                    "severity": "high",
                    "url": "Jenkins build URL"
                })
            
            if "quality gate" in analysis_lower and "fail" in analysis_lower:
                findings["failed_checks"].append({
                    "name": "Quality Gate",
                    "status": "failed",
                    "details": "Quality Gate failed - code quality issues detected", 
                    "severity": "high",
                    "url": "SonarQube URL"
                })
            
            # Extract health issues
            if "ci workflow" in analysis_lower and ("not complete" in analysis_lower or "failed" in analysis_lower):
                findings["health_issues"].append({
                    "type": "ci_workflow",
                    "status": "failed",
                    "details": "CI Workflow did not complete successfully",
                    "severity": "high"
                })
            
            # Extract code review feedback
            if "review" in analysis_lower and ("comment" in analysis_lower or "feedback" in analysis_lower):
                findings["code_review_feedback"].append({
                    "reviewer": "Reviewer extracted from analysis",
                    "state": "commented",
                    "body": "Code review feedback extracted from analysis",
                    "file": "File path extracted from analysis"
                })
            
            # Extract issue comments
            if "comment" in analysis_lower and "issue" in analysis_lower:
                findings["issue_comments"].append({
                    "author": "Comment author extracted from analysis",
                    "body": "Issue comment extracted from analysis",
                    "created_at": "Timestamp extracted from analysis",
                    "type": "general"
                })
            
            # Extract bot notifications
            if "bot" in analysis_lower or "notification" in analysis_lower:
                findings["bot_notifications"].append({
                    "bot": "Bot name extracted from analysis",
                    "message": "Bot notification extracted from analysis",
                    "type": "ci_failure"
                })
            
            # Extract workflow runs
            if "workflow" in analysis_lower:
                findings["workflow_runs"].append({
                    "name": "Workflow name extracted from analysis",
                    "status": "failure" if "fail" in analysis_lower else "success",
                    "conclusion": "failure" if "fail" in analysis_lower else "success",
                    "url": "Workflow URL extracted from analysis"
                })
            
            # Extract errors
            if "jenkins" in analysis_lower and "fail" in analysis_lower:
                findings["errors"].append({
                    "source": "jenkins",
                    "error": "Jenkins build failure detected in CI/CD pipeline",
                    "severity": "high"
                })
            
            # Add comprehensive recommendations
            findings["recommendations"] = [
                "Check Jenkins build logs for specific failure details",
                "Address any code review feedback from reviewers",
                "Review Quality Gate configuration and fix code quality issues", 
                "Ensure all required checks pass before merge",
                "Check workflow run details for specific failure reasons",
                "Contact DevOps team if infrastructure issues persist"
            ]
            
            findings["summary"] = "Comprehensive GitHub PR analysis found multiple issues requiring attention"
        
        return findings

    def _display_comprehensive_github_analysis(self, findings: Dict[str, Any], user_prompt: str):
        """Display comprehensive GitHub analysis in detailed format like github.py"""
        
        print(f"\n🎯 PR Checks & Comments: {user_prompt}")
        print(f"\n🔍 Processing: {user_prompt}")
        print(f"\n📊 Analysis:")
        print("=" * 40)
        
        # Extract PR number from user prompt for title
        pr_number = "Unknown"
        if "pull/" in user_prompt:
            try:
                pr_number = user_prompt.split("pull/")[1].split("/")[0]
            except:
                pass
        
        print(f"### Pull Request Analysis for PR #{pr_number}")
        print()
        
        # PR Metadata Section
        pr_metadata = findings.get('pr_metadata', {})
        if pr_metadata:
            print("#### **PR Metadata**")
            title = pr_metadata.get('title', 'Unknown')
            author = pr_metadata.get('author', 'Unknown')
            state = pr_metadata.get('state', 'Unknown')
            labels = pr_metadata.get('labels', [])
            commits = pr_metadata.get('commits', 0)
            additions = pr_metadata.get('additions', 0)
            deletions = pr_metadata.get('deletions', 0)
            changed_files = pr_metadata.get('changed_files', 0)
            
            print(f"- **Title:** {title}")
            print(f"- **Author:** @{author}")
            print(f"- **State:** {state.title()}")
            if labels:
                print(f"- **Labels:** `{', '.join(labels)}`")
            if commits > 0:
                print(f"- **Commits:** {commits}")
                print(f"- **Additions:** {additions} lines")
                print(f"- **Deletions:** {deletions} lines")
                print(f"- **Changed Files:** {changed_files}")
            print()
        
        # CI/CD Check Status Section
        ci_cd_status = findings.get('ci_cd_status', {})
        failed_checks = findings.get('failed_checks', [])
        workflow_runs = findings.get('workflow_runs', [])
        
        print("#### **CI/CD Check Status**")
        overall_status = ci_cd_status.get('overall_status', 'unknown')
        total_checks = ci_cd_status.get('total_checks', 0)
        passed_checks = ci_cd_status.get('passed_checks', 0)
        failed_checks_count = ci_cd_status.get('failed_checks', 0)
        
        if overall_status == 'success':
            print("- **Build Status:** All CI/CD checks have passed successfully.")
        elif overall_status == 'failure':
            print("- **Build Status:** CI/CD checks have failed.")
        else:
            print("- **Build Status:** CI/CD checks are pending or unknown.")
        
        if total_checks > 0:
            print("- **Details:**")
            print(f"  - Total Checks: {total_checks}")
            print(f"  - Passed: {passed_checks}")
            print(f"  - Failed: {failed_checks_count}")
            print(f"  - Pending: {total_checks - passed_checks - failed_checks_count}")
        
        if failed_checks:
            print("- **Failed Checks:**")
            for i, check in enumerate(failed_checks, 1):
                check_name = check.get('name', 'Unknown')
                check_details = check.get('details', 'No details')
                check_url = check.get('url', '')
                print(f"  - **{check_name}:** {check_details}")
                if check_url:
                    print(f"    - [Check Details]({check_url})")
        
        if workflow_runs:
            print("- **Workflow Runs:**")
            for workflow in workflow_runs:
                name = workflow.get('name', 'Unknown')
                status = workflow.get('status', 'unknown')
                conclusion = workflow.get('conclusion', 'unknown')
                url = workflow.get('url', '')
                print(f"  - **{name}:** {status} ({conclusion})")
                if url:
                    print(f"    - [Workflow Details]({url})")
        print()
        
        # Code Review Feedback Section
        code_reviews = findings.get('code_review_feedback', [])
        if code_reviews:
            print("#### **Code Review Feedback**")
            print("- **Review Comments:**")
            for i, review in enumerate(code_reviews, 1):
                reviewer = review.get('reviewer', 'Unknown')
                state = review.get('state', 'commented')
                body = review.get('body', 'No comment')
                file_path = review.get('file', '')
                
                print(f"  - **Comment {i}:** \"{body[:100]}{'...' if len(body) > 100 else ''}\" (by @{reviewer})")
                if file_path:
                    print(f"    on `{file_path}`")
            
            # Group reviews by state
            approved_by = [r.get('reviewer') for r in code_reviews if r.get('state') == 'approved']
            changes_requested_by = [r.get('reviewer') for r in code_reviews if r.get('state') == 'changes_requested']
            
            if approved_by:
                print("- **Review Approvals:**")
                print(f"  - Approved by @{', @'.join(approved_by)}")
            
            if changes_requested_by:
                print("- **Changes Requested:**")
                print(f"  - Changes requested by @{', @'.join(changes_requested_by)}")
            print()
        
        # Issue Comments Section
        issue_comments = findings.get('issue_comments', [])
        bot_notifications = findings.get('bot_notifications', [])
        
        if issue_comments or bot_notifications:
            print("#### **Issue Comments**")
            
            if issue_comments:
                print("- **General Comments:**")
                for i, comment in enumerate(issue_comments, 1):
                    author = comment.get('author', 'Unknown')
                    body = comment.get('body', 'No comment')
                    created_at = comment.get('created_at', '')
                    print(f"  - **Comment {i}:** \"{body[:100]}{'...' if len(body) > 100 else ''}\" (by @{author})")
                    if created_at:
                        print(f"    - Posted: {created_at}")
            
            if bot_notifications:
                print("- **Bot Notifications:**")
                for notification in bot_notifications:
                    bot = notification.get('bot', 'Unknown Bot')
                    message = notification.get('message', 'No message')
                    notif_type = notification.get('type', 'general')
                    print(f"  - **{bot}:** {message[:100]}{'...' if len(message) > 100 else ''}")
                    print(f"    - Type: {notif_type}")
            print()
        
        # Health Issues Section
        health_issues = findings.get('health_issues', [])
        if health_issues:
            print("#### **Health Issues**")
            for issue in health_issues:
                issue_type = issue.get('type', 'Unknown')
                issue_details = issue.get('details', 'No details')
                severity = issue.get('severity', 'medium')
                print(f"- **{issue_type.title()}:** {issue_details}")
                print(f"  - Severity: {severity}")
            print()
        
        # Errors Section
        errors = findings.get('errors', [])
        if errors:
            print("#### **Errors**")
            for error in errors:
                source = error.get('source', 'Unknown')
                error_msg = error.get('error', 'No error message')
                severity = error.get('severity', 'medium')
                print(f"- **{source.title()}:** {error_msg}")
                print(f"  - Severity: {severity}")
            print()
        
        # Summary Section
        print("---")
        print()
        print("### **Summary of PR Health**")
        
        # Overall status determination
        if overall_status == 'success' and not failed_checks and not health_issues:
            print("- **CI/CD Status:** ✅ All checks passed successfully.")
            print("- **Overall Health:** The PR is in good health.")
        elif overall_status == 'failure' or failed_checks or health_issues:
            print("- **CI/CD Status:** ❌ Issues detected requiring attention.")
            if failed_checks:
                print(f"- **Failed Checks:** {len(failed_checks)} checks failed")
            if health_issues:
                print(f"- **Health Issues:** {len(health_issues)} issues found")
            print("- **Overall Health:** The PR requires fixes before merge.")
        else:
            print("- **CI/CD Status:** ⏳ Checks are pending or status unknown.")
            print("- **Overall Health:** Awaiting CI/CD completion.")
        
        if code_reviews:
            approved_count = len([r for r in code_reviews if r.get('state') == 'approved'])
            if approved_count > 0:
                print("- **Code Review:** Received approvals from reviewers.")
            else:
                print("- **Code Review:** Awaiting reviewer approvals.")
        
        print()
        print("If you need further details or assistance, let me know!")
        print()