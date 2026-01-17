# ============================================
# FILE: app/core/llm_chain.py
# ============================================
"""
LLM chain for generating answers using Groq.
"""

from typing import List, Dict, Any, Optional
from groq import Groq

from app.config import settings
from app.utils import get_logger, LLMError
from app.models import RetrievedDocument

logger = get_logger(__name__)


class LLMChain:
    """Orchestrates LLM calls for answer generation."""
    
    def __init__(self):
        """Initialize Groq client."""
        try:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
            logger.info("llm_chain_initialized", model=settings.LLM_MODEL)
        except Exception as e:
            logger.error("llm_init_failed", error=str(e))
            raise LLMError(f"Failed to initialize LLM: {e}")
    
    def _build_context(self, documents: List[RetrievedDocument]) -> str:
        """Build context string from retrieved documents."""
        if not documents:
            return "No relevant IPC sections found in the database."
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            context_parts.append(
                f"[Source {i}] Section {doc.section}: {doc.title}\n{doc.text}"
            )
        
        context = "\n\n".join(context_parts)
        
        if len(context) > settings.MAX_CONTEXT_LENGTH:
            logger.warning("context_truncated", 
                          original_length=len(context),
                          max_length=settings.MAX_CONTEXT_LENGTH)
            context = context[:settings.MAX_CONTEXT_LENGTH] + "..."
        
        return context
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for the LLM."""
        return """You are a helpful and knowledgeable Indian Legal Assistant specializing in the Indian Penal Code (IPC).

Your responsibilities:
1. Provide accurate information based on the IPC sections provided in the context
2. Cite specific section numbers when answering
3. Explain legal concepts in clear, accessible language
4. If the context doesn't contain relevant information, clearly state that
5. Never make up or hallucinate section numbers or legal provisions
6. Maintain a professional, helpful tone

When answering:
- Start with a direct answer to the user's question
- Reference specific section numbers from the context
- Provide brief explanations of legal terms if needed
- Keep answers concise but complete"""
    
    def _build_user_prompt(self, query: str, context: str) -> str:
        """Build user prompt combining query and context."""
        return f"""Context from Indian Penal Code:
{context}

User Question: {query}

Please provide an accurate answer based on the context above. If the context doesn't contain relevant information to answer the question, clearly state that."""
    
    def generate_answer(
        self,
        query: str,
        documents: List[RetrievedDocument],
        chat_history: List[Dict[str, str]] = None
    ) -> str:
        """Generate answer using LLM."""
        try:
            context = self._build_context(documents)
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(query, context)
            
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            if chat_history:
                messages.extend(chat_history)
            
            messages.append({"role": "user", "content": user_prompt})
            
            logger.info("generating_answer", 
                       query=query[:50],
                       context_length=len(context),
                       has_history=bool(chat_history))
            
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )
            
            answer = response.choices[0].message.content.strip()
            
            logger.info("answer_generated",
                       query=query[:50],
                       answer_length=len(answer),
                       model=settings.LLM_MODEL)
            
            return answer
            
        except Exception as e:
            logger.error("llm_generation_failed",
                        query=query[:50],
                        error=str(e))
            raise LLMError(f"Failed to generate answer: {e}")


_llm_chain: Optional[LLMChain] = None


def get_llm_chain() -> LLMChain:
    """Get or create the global LLMChain instance."""
    global _llm_chain
    if _llm_chain is None:
        _llm_chain = LLMChain()
    return _llm_chain