"""
Handles the generation of final, developer-focused summaries from agent findings.
"""

from ..utils.rag_service import rag_service
from typing import Dict, Any

class Summarizer:
    """Generates final developer-focused summaries."""
    def _generate_final_developer_summary(self, github_findings, kubernetes_findings, jenkins_findings) -> str:
        """Generate the final developer-focused summary"""
        
        # Determine which findings are available
        active_findings = []
        if github_findings: active_findings.append("GitHub")
        if kubernetes_findings: active_findings.append("Kubernetes")
        if jenkins_findings: active_findings.append("Jenkins")
        
        summary = f"""
            🎯 **DEVOPS ANALYSIS COMPLETE** ({', '.join(active_findings)})
            ============================================================
            """
        
        # Add findings from each active agent
        if kubernetes_findings:
            summary += self._format_kubernetes_summary(kubernetes_findings)
        
        if github_findings:
            summary += self._format_github_summary(github_findings)
            
        if jenkins_findings:
            summary += self._format_jenkins_summary(jenkins_findings)
        
        return summary

    def _format_kubernetes_summary(self, findings):
        """Format Kubernetes findings for developer summary"""
        print(f"🔍 DEBUG: Formatting K8s summary, findings keys: {list(findings.keys()) if findings else 'None'}")
        print(f"🔍 DEBUG: Has intelligent_analysis: {bool(findings.get('intelligent_analysis')) if findings else False}")

        if findings.get('intelligent_analysis'):
            analysis = findings['intelligent_analysis']
            root_cause = analysis.get('root_cause', 'Under investigation')
            developer_actions = analysis.get('developer_actions', [])
            problem_summary = analysis.get('problem_summary', 'Issue detected')
            print(f"🔍 DEBUG: Using intelligent analysis: {problem_summary}")

        else:
            # Fallback to basic findings
            root_cause = findings.get('root_cause', 'Under investigation')
            developer_actions = findings.get('developer_actions', [])
            problem_summary = findings.get('problem_summary', 'Issue detected')
            print(f"🔍 DEBUG: Using fallback analysis: {problem_summary}")
        
        # Format developer actions properly
        actions_text = ""
        if developer_actions:
            if isinstance(developer_actions, list):
                actions_text = "\n".join([f"  - {action}" for action in developer_actions])
            else:
                actions_text = str(developer_actions)
        else:
            actions_text = "No specific actions identified"
        
        return f"""
        ☸️ **KUBERNETES ANALYSIS**:
        • Problem: {problem_summary}
        • Root Cause: {root_cause}
        • Actions: {len(developer_actions) if isinstance(developer_actions, list) else 0} action items
        • Action Details:
        {actions_text}
        """
    
    def _format_github_summary(self, findings):
        """Format GitHub findings for developer summary"""
        return f"""
        🔧 **GITHUB ANALYSIS**:
        • PR Status: {findings.get('pr_health', 'Unknown')}
        • CI Status: {findings.get('ci_status', 'Unknown')}
        • Issues: {len(findings.get('issues', []))} identified
        
        """

    def _format_jenkins_summary(self, findings):
        """Format Jenkins findings for developer summary"""
        return f"""
        🏗️ **JENKINS ANALYSIS**:
        • Build Status: {findings.get('build_status', 'Unknown')}
        • Root Cause: {findings.get('root_cause', 'Under investigation')}
        • Actions: {len(findings.get('recommendations', []))} recommendations                
        """
    async def generate_correlated_summary(self, github_findings, kubernetes_findings, jenkins_findings, correlation_analysis, historical_solutions, state) -> str:
        """NEW: Generate INTELLIGENT CORRELATED summary with RAG integration"""
        
        # Extract findings from AgentResponse objects if needed
        if hasattr(github_findings, 'findings'):
            github_findings = github_findings.findings
        if hasattr(kubernetes_findings, 'findings'):
            kubernetes_findings = kubernetes_findings.findings
        if hasattr(jenkins_findings, 'findings'):
            jenkins_findings = jenkins_findings.findings
        
        # Get historical solutions if not provided
        if not historical_solutions and rag_service:
            try:
                context = self._create_rag_context(github_findings, kubernetes_findings, jenkins_findings, state)
                historical_solutions = await rag_service.get_historical_solutions(
                    state.get("user_prompt", ""), 
                    context
                )
            except Exception as e:
                print(f"⚠️ RAG service failed: {str(e)}")
                historical_solutions = None
        
        lines = []
        lines.append("🎯 INTELLIGENT DEVOPS CORRELATION ANALYSIS")
        lines.append("=" * 60)
        
        # NEW: Show correlation results first (most important)
        if correlation_analysis and correlation_analysis.get("correlation_found"):
            lines.append(f"\n🧠 INTELLIGENT CORRELATION FOUND:")
            lines.append(f"   • Type: {correlation_analysis.get('correlation_type', 'unknown').replace('_', ' ').upper()}")
            lines.append(f"   • Confidence: {correlation_analysis.get('correlation_confidence', 'unknown').upper()}")
            
            # Show primary issue and root cause
            primary_issue = correlation_analysis.get('Problem', 'Unknown issue')
            root_cause = correlation_analysis.get('root_cause', 'Unknown root cause')
            unified_solution = correlation_analysis.get('unified_solution', 'No unified solution available')
            
            lines.append(f"\n🎯 **CORRELATED ISSUE**:")
            lines.append(f"   • Primary Issue: {primary_issue}")
            lines.append(f"   • Root Cause: {root_cause}")
            lines.append(f"   • Unified Solution: {unified_solution}")
            
            # Show correlation evidence
            evidence = correlation_analysis.get('evidence', [])
            if evidence:
                lines.append(f"\n🔗 **CORRELATION EVIDENCE**:")
                for i, ev in enumerate(evidence[:3], 1):  # Show top 3 evidence points
                    lines.append(f"   {i}. {ev}")
            
            # Show immediate actions from correlation
            immediate_actions = correlation_analysis.get('immediate_actions', [])
            if immediate_actions:
                lines.append(f"\n⚡ **CORRELATED ACTIONS**:")
                lines.append(f"   • {len(immediate_actions)} coordinated action items")
                for i, action in enumerate(immediate_actions[:3], 1):
                    lines.append(f"     {i}. {action}")
        else:
            lines.append(f"\n🧠 CORRELATION ANALYSIS:")
            lines.append(f"   • No clear correlation found between systems")
            lines.append(f"   • Issues may be independent or require separate investigation")        
        # GitHub Analysis Results (COMPREHENSIVE)
        if github_findings:
            lines.append(f"\n🔧 **GITHUB ANALYSIS**:")
            lines.append(f"   • Status: {github_findings.get('status', 'success')}")
            
            # Use standardized format fields
            # problem_identified = github_findings.get('problem_identified', 'Issue detected')
            # root_cause = github_findings.get('root_cause', 'Under investigation')
            analysis = github_findings.get('analysis', {})
            intelligent_analysis = github_findings.get('intelligent_analysis', {})
            health_check_info = github_findings.get('health_check_info', {})
            if intelligent_analysis:
                problem_identified = intelligent_analysis.get('problem_summary', 'GitHub analysis completed')
                root_cause = intelligent_analysis.get('root_cause', 'GitHub PR analyzed')
                solution = intelligent_analysis.get('developer_actions', [])
            elif health_check_info and health_check_info.get('failures'):
                # Use health check failure information
                failures = health_check_info.get('failures', [])
                applications = health_check_info.get('applications', [])
                environment = health_check_info.get('environment', 'unknown')
                
                problem_identified = f"Health check failures detected for applications: {', '.join(applications)} in {environment} environment"
                root_cause = f"Found {len(failures)} health check failure patterns including ArgoCD sync issues and missing configuration files"
                solution = [
                    f"Check ArgoCD application sync status for {', '.join(applications)}",
                    f"Verify values_properties files are present and correctly configured",
                    f"Investigate GetValuesPropertiesFileActivity and GetArgoAppSyncStatusActivity failures"
                ]
            elif analysis:
                # Use regular analysis fields if available
                problem_identified = analysis.get('problem_summary', github_findings.get('problem_identified', 'GitHub PR analyzed'))
                root_cause = analysis.get('root_cause', github_findings.get('root_cause', 'PR status determined'))
                solution = github_findings.get('solution', analysis.get('recommendations', []))
            else:
                # Final fallback - but make it meaningful
                problem_identified = github_findings.get('problem_identified', 'GitHub PR analysis completed')
                root_cause = github_findings.get('root_cause', 'PR review completed')
                solution = github_findings.get('solution', [])

            lines.append(f"   • Problem: {problem_identified}")
            lines.append(f"   • Root Cause: {root_cause}")
            
            if solution:
                lines.append(f"   • Actions: {len(solution)} action items")
                for i, action in enumerate(solution[:3], 1):  # Show top 3 actions
                    lines.append(f"     {i}. {action}")
            else:
                lines.append(f"   • Actions: No specific actions identified")
            
            # Show PR metadata
            pr_metadata = github_findings.get('pr_metadata', {})
            if pr_metadata:
                title = pr_metadata.get('title', 'Unknown')
                author = pr_metadata.get('author', 'Unknown')
                state = pr_metadata.get('state', 'Unknown')
                lines.append(f"   • PR: {title} by {author} ({state})")
                
                commits = pr_metadata.get('commits', 0)
                additions = pr_metadata.get('additions', 0)
                deletions = pr_metadata.get('deletions', 0)
                if commits > 0:
                    lines.append(f"   • Changes: {commits} commits, +{additions}/-{deletions} lines")
            
            # Show CI/CD status
            ci_cd_status = github_findings.get('ci_cd_status', {})
            if ci_cd_status:
                overall_status = ci_cd_status.get('overall_status', 'unknown')
                total_checks = ci_cd_status.get('total_checks', 0)
                failed_checks_count = ci_cd_status.get('failed_checks', 0)
                lines.append(f"   • CI/CD: {overall_status} ({failed_checks_count}/{total_checks} failed)")
            
            # Show failed checks with details
            failed_checks = github_findings.get('failed_checks', [])
            if failed_checks:
                lines.append(f"   • Failed Checks: {len(failed_checks)}")
                for check in failed_checks[:2]:  # Show top 2
                    check_name = check.get('name', 'Unknown')
                    check_details = check.get('details', 'No details')[:60]
                    lines.append(f"     - {check_name}: {check_details}...")
            
            # Show code review feedback
            code_reviews = github_findings.get('code_review_feedback', [])
            if code_reviews:
                lines.append(f"   • Code Reviews: {len(code_reviews)} feedback items")
                for review in code_reviews[:1]:  # Show top 1
                    reviewer = review.get('reviewer', 'Unknown')
                    state = review.get('state', 'commented')
                    lines.append(f"     - {reviewer}: {state}")
            
            # Show issue comments
            issue_comments = github_findings.get('issue_comments', [])
            if issue_comments:
                lines.append(f"   • Issue Comments: {len(issue_comments)} comments")
            
            # Show bot notifications
            bot_notifications = github_findings.get('bot_notifications', [])
            if bot_notifications:
                lines.append(f"   • Bot Notifications: {len(bot_notifications)} notifications")
            
            # Show workflow runs
            workflow_runs = github_findings.get('workflow_runs', [])
            if workflow_runs:
                lines.append(f"   • Workflow Runs: {len(workflow_runs)} runs")
                for workflow in workflow_runs[:1]:  # Show top 1
                    name = workflow.get('name', 'Unknown')
                    status = workflow.get('status', 'unknown')
                    lines.append(f"     - {name}: {status}")
            
            # Show health issues
            health_issues = github_findings.get('health_issues', [])
            if health_issues:
                lines.append(f"   • Health Issues: {len(health_issues)}")
        
        # Kubernetes Analysis Results (DETAILED)
        if kubernetes_findings:
            lines.append(f"\n☸️ **KUBERNETES ANALYSIS**:")
            lines.append(f"   • Status: {kubernetes_findings.get('status', 'success')}")
            environment = kubernetes_findings.get('environment', 'unknown')
            namespaces = kubernetes_findings.get('namespaces_analyzed', [])
            business_unit = kubernetes_findings.get('business_unit', 'unknown')

            lines.append(f"   • Namespace: {', '.join(namespaces) if namespaces else 'unknown'}")
            lines.append(f"   • Environment: {environment.upper()}")
            
            # Pod health summary
            unhealthy_pods = kubernetes_findings.get('unhealthy_pods', [])
            healthy_pods = kubernetes_findings.get('healthy_pods', [])
            lines.append(f"   • Pod Health: {len(healthy_pods)} healthy, {len(unhealthy_pods)} unhealthy")
            
            # Use standardized format fields
            # problem_identified = kubernetes_findings.get('problem_identified', 'Issue detected')
            # root_cause = kubernetes_findings.get('root_cause', 'Under investigation')
            # solution = kubernetes_findings.get('solution', [])
            intelligent_analysis = kubernetes_findings.get('intelligent_analysis', {})
            if intelligent_analysis:
                problem_identified = intelligent_analysis.get('problem_summary', 'Issue detected')
                root_cause = intelligent_analysis.get('root_cause', 'Under investigation')
                solution = intelligent_analysis.get('developer_actions', [])
            else:
                # Fallback to generic fields
                problem_identified = kubernetes_findings.get('problem_identified', 'Analysis completed')
                root_cause = kubernetes_findings.get('root_cause', 'Investigation completed')
                solution = kubernetes_findings.get('solution', [])
            lines.append(f"   • Problem: {problem_identified}")
            lines.append(f"   • Root Cause: {root_cause}")
            
            if solution:
                lines.append(f"   • Actions: {len(solution)} action items")
                for i, action in enumerate(solution[:3], 1):  # Show top 3 actions
                    lines.append(f"     {i}. {action}")
            else:
                lines.append(f"   • Actions: No specific actions identified")
        
        # Jenkins Analysis Results (DETAILED)
        if jenkins_findings:
            lines.append(f"\n🏗️ **JENKINS ANALYSIS**:")
            lines.append(f"   • Status: {jenkins_findings.get('status', 'success')}")
            
            # Use standardized format fields
            problem_identified = jenkins_findings.get('problem_identified', 'Issue detected')
            root_cause = jenkins_findings.get('root_cause', 'Under investigation')
            solution = jenkins_findings.get('solution', [])
            
            lines.append(f"   • Problem: {problem_identified}")
            lines.append(f"   • Root Cause: {root_cause}")
            
            if solution:
                lines.append(f"   • Actions: {len(solution)} action items")
                for i, action in enumerate(solution[:3], 1):  # Show top 3 actions
                    lines.append(f"     {i}. {action}")
            else:
                lines.append(f"   • Actions: No specific actions identified")
            
            # Build info
            build_info = jenkins_findings.get('build_info', {})
            if build_info:
                environment = build_info.get('environment', 'unknown')
                build_number = build_info.get('build_number', 'unknown')
                build_status = build_info.get('build_status', 'unknown')
                lines.append(f"   • Environment: {environment.upper()}")
                lines.append(f"   • Build: #{build_number} ({build_status})")
        
        # NEW: Historical solutions from RAG
        if historical_solutions and historical_solutions.get("solutions_found"):
            lines.append(f"\n📚 HISTORICAL SOLUTIONS FOUND:")
            lines.append(f"   • {historical_solutions.get('message', 'Found historical solutions')}")
            
            # Show top historical solutions
            solutions = historical_solutions.get("recommended_solutions", [])
            if solutions:
                lines.append(f"   • Top Historical Solutions:")
                for i, solution in enumerate(solutions[:3], 1):  # Show top 3
                    jira_id = solution.get("jira_id", "Unknown")
                    similarity = solution.get("similarity_score", 0.0)
                    solution_text = solution.get("solution", "")
                    summary = solution.get("summary", "")
                    root_cause = solution.get("root_cause", "")
                    
                    lines.append(f"     {i}. [{jira_id}] (Similarity: {similarity:.2f})")
                    if summary:
                        lines.append(f"        Summary: {summary}")
                    if root_cause:
                        lines.append(f"        Root Cause: {root_cause}")
                    if solution_text:
                        # Show complete solution, not truncated
                        lines.append(f"        Solution: {solution_text}")
                    lines.append("")  # Empty line for readability
            
            # Show recommendations
            recommendations = historical_solutions.get("recommendations", [])
            if recommendations:
                lines.append(f"   • AI Recommendations:")
                for rec in recommendations[:3]:  # Show top 3
                    lines.append(f"     - {rec}")
        
        # NEW: Correlation-based recommendations
        if correlation_analysis and correlation_analysis.get("actionable_solution"):
            lines.append(f"\n⚡ CORRELATED SOLUTION:")
            lines.append(f"   {correlation_analysis['actionable_solution']}")
        
        # Overall Status with correlation context
        critical_issues = 0
        if kubernetes_findings:
            critical_issues += len(kubernetes_findings.get('unhealthy_pods', []))
        if github_findings:
            critical_issues += len([c for c in github_findings.get('failed_checks', []) if c.get('severity') == 'high'])
        
        if correlation_analysis and correlation_analysis.get("correlation_found"):
            correlation_type = correlation_analysis.get('correlation_type', 'unknown').replace('_', ' ').title()
            priority = correlation_analysis.get('priority', 'medium')
            
            if priority == 'critical':
                status_icon = "🔴"
                status_text = "CRITICAL CORRELATED ISSUE"
            elif priority == 'high':
                status_icon = "🟠" 
                status_text = "HIGH PRIORITY CORRELATED ISSUE"
            else:
                status_icon = "🟡"
                status_text = "CORRELATED ISSUE"
            lines.append(f"\n{status_icon} STATUS: {status_text}: {correlation_type} problem identified")
        else:
            issue_count = sum([
                1 if github_findings and github_findings.get('problem_identified') else 0,
                1 if kubernetes_findings and kubernetes_findings.get('problem_identified') else 0,
                1 if jenkins_findings and jenkins_findings.get('problem_identified') else 0
            ])
            
            if issue_count > 0:
                lines.append(f"\n🟡 STATUS: ISSUES FOUND: {issue_count} issues require investigation")
            else:
                lines.append(f"\n🟢 STATUS: No critical issues found")
                
                # lines.append(f"\n{status_emoji} STATUS: {status_text}")
                # lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _create_rag_contextV0(self, github_findings, kubernetes_findings, jenkins_findings, state) -> Dict[str, Any]:
        """Create context for RAG service from current findings"""
        context = {}
        
        # Extract findings from AgentResponse objects if needed
        if hasattr(kubernetes_findings, 'findings'):
            kubernetes_findings = kubernetes_findings.findings
        if hasattr(github_findings, 'findings'):
            github_findings = github_findings.findings
        if hasattr(jenkins_findings, 'findings'):
            jenkins_findings = jenkins_findings.findings
        
        # Extract namespace and environment from Kubernetes findings
        if kubernetes_findings:
            context["namespace"] = kubernetes_findings.get("namespace")
            context["environment"] = kubernetes_findings.get("environment")
            
            # Extract services from unhealthy pods
            unhealthy_pods = kubernetes_findings.get("unhealthy_pods", [])
            services = []
            for pod in unhealthy_pods:
                pod_name = pod.get("name", "")
                if pod_name:
                    # Extract service name from pod name (remove deployment hash)
                    import re
                    service_name = re.sub(r'-[a-z0-9]{8,10}-[a-z0-9]{5}$', '', pod_name)
                    service_name = re.sub(r'-[0-9]+$', '', service_name)
                    if service_name not in services:
                        services.append(service_name)
            context["services"] = services
            
            # Extract issue type and error patterns
            root_causes = kubernetes_findings.get("root_causes", [])
            context["issue_type"] = kubernetes_findings.get("issue_type", "unknown")
            context["error_patterns"] = root_causes
        
        # Extract GitHub context
        if github_findings:
            failed_checks = github_findings.get("failed_checks", [])
            error_patterns = []
            for check in failed_checks:
                if check.get("details"):
                    error_patterns.append(check["details"])
            if error_patterns:
                context["error_patterns"] = context.get("error_patterns", []) + error_patterns
        
        # Extract Jenkins context
        if jenkins_findings:
            analysis = jenkins_findings.get("analysis", {})
            if analysis.get("error_details"):
                context["error_patterns"] = context.get("error_patterns", []) + analysis["error_details"]
        
        return context
    
