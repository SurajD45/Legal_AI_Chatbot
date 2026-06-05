"""
Core application services.

This module exposes ONLY public, production-safe entry points.
"""

from app.core.retriever import DocumentRetriever, get_retriever
from app.core.llm_chain import LLMChain, get_llm_chain
from app.core.chat_history import ChatHistoryManager, get_history_manager
from app.core.query_condenser import QueryCondenser, get_query_condenser
from app.core.context_expander import ContextExpander, get_context_expander

__all__ = [
    "DocumentRetriever",
    "get_retriever",
    "LLMChain",
    "get_llm_chain",
    "ChatHistoryManager",
    "get_history_manager",
    "QueryCondenser",
    "get_query_condenser",
    "ContextExpander",
    "get_context_expander",
]
