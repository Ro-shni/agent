"""
Prompts package for Kairos.
This package contains all LLM prompts, categorized by their domain
(e.g., orchestrator, kubernetes, summarizer).
"""
from .shared import SafeDict
from .orchestrator import ORCHESTRATOR_SYSTEM_PROMPT,ORCHESTRATOR_USER_PROMPT_TEMPLATE, get_orchestrator_prompt
from .kubernetes import (
    KUBERNETES_SYSTEM_PROMPT,
    GENERIC_CONTAINER_ANALYSIS_PROMPT,
    NO_LOGS_CONTAINER_ANALYSIS_PROMPT
)
from .summarizer import INTELLIGENT_SUMMARIZER_PROMPT, get_intelligent_summarizer_prompt
from .correlation import CORRELATION_SYSTEM_PROMPT, get_correlation_analysis_prompt
from .analysis import ERROR_ANALYSIS_PROMPT, URL_ANALYSIS_PROMPT, HEALTH_CHECK_PROMPT

__all__ = [
    "SafeDict",
    # "get_analysis_mode",
    # "format_prompt_safely",
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "ORCHESTRATOR_USER_PROMPT_TEMPLATE",
    "get_orchestrator_prompt",
    "KUBERNETES_SYSTEM_PROMPT",
    "GENERIC_CONTAINER_ANALYSIS_PROMPT",
    "NO_LOGS_CONTAINER_ANALYSIS_PROMPT",
    "INTELLIGENT_SUMMARIZER_PROMPT",
    "get_intelligent_summarizer_prompt",
    "CORRELATION_SYSTEM_PROMPT",
    "get_correlation_analysis_prompt",
    "ERROR_ANALYSIS_PROMPT",
    "URL_ANALYSIS_PROMPT",
    "HEALTH_CHECK_PROMPT",
]