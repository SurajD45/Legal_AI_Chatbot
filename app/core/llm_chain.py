"""
LLM chain for generating answers using Groq.
Production-safe version (Railway compatible).
"""

from typing import List, Dict, Optional
from groq import Groq

from app.config import settings
from app.utils import get_logger, LLMError
from app.models import RetrievedDocument

logger = get_logger(__name__)


SAFE_FALLBACK_MODEL = "llama-3.1-8b-instant"


class LLMChain:
    """Orchestrates LLM calls for IPC-based legal answers."""

    def __init__(self):
        try:
            model = settings.LLM_MODEL or SAFE_FALLBACK_MODEL

            self.client = Groq(
                api_key=settings.GROQ_API_KEY,
                timeout=60,              # 🔥 CRITICAL FIX
            )

            self.model = model
            logger.info("llm_chain_initialized", model=model)

        except Exception as e:
            logger.error("llm_init_failed", error=str(e))
            raise LLMError(f"Failed to initialize LLM: {e}")

    # --------------------------------------------------
    # Context builder
    # --------------------------------------------------
    def _build_context(self, documents: List[RetrievedDocument]) -> str:
        if not documents:
            return "No relevant IPC sections were found."

        parts = []
        for idx, doc in enumerate(documents, 1):
            parts.append(
                f"[Source {idx}]\n"
                f"Section {doc.section}: {doc.title}\n"
                f"{doc.text}"
            )

        context = "\n\n".join(parts)

        if len(context) > settings.MAX_CONTEXT_LENGTH:
            context = context[: settings.MAX_CONTEXT_LENGTH] + "..."

        return context

    # --------------------------------------------------
    # SYSTEM PROMPT
    # --------------------------------------------------
    def _build_system_prompt(self) -> str:
        return """
You are an Indian Legal Assistant specializing in the Indian Penal Code (IPC).

RULES:
- Use ONLY provided IPC context
- Consolidate related punishment sections
- Never say "punishment not specified" if related sections exist
- Bullet points only
- No hallucination

FORMAT:

RELEVANT PROVISIONS:
- Section XXX: Title

ANALYSIS:
- Bullet points

PUNISHMENT:
- Bullet points
- Mention IPC section
"""

    # --------------------------------------------------
    # USER PROMPT
    # --------------------------------------------------
    def _build_user_prompt(self, query: str, context: str) -> str:
        return f"""
IPC CONTEXT:
{context}

QUESTION:
{query}
"""

    # --------------------------------------------------
    # MAIN GENERATION
    # --------------------------------------------------
    def generate_answer(
        self,
        query: str,
        documents: List[RetrievedDocument],
        chat_history: List[Dict[str, str]] = None,
    ) -> str:
        try:
            context = self._build_context(documents)

            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": self._build_user_prompt(query, context)},
            ]

            logger.info(
                "calling_groq",
                model=self.model,
                context_length=len(context),
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=700,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error("groq_call_failed", error=str(e))
            raise LLMError(f"Failed to generate answer: {e}")


# Singleton
_llm_chain: Optional[LLMChain] = None


def get_llm_chain() -> LLMChain:
    global _llm_chain
    if _llm_chain is None:
        _llm_chain = LLMChain()
    return _llm_chain
