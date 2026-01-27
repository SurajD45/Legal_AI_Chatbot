"""
LLM chain for generating answers using Groq.

Optimized for legal readability:
- Bullet points
- Section highlighting
- Clear punishments
- No wall-of-text answers
"""

from typing import List, Dict, Optional
from groq import Groq

from app.config import settings
from app.utils import get_logger, LLMError
from app.models import RetrievedDocument

logger = get_logger(__name__)


class LLMChain:
    """Orchestrates LLM calls for IPC-based legal answers."""

    def __init__(self):
        try:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
            logger.info("llm_chain_initialized", model=settings.LLM_MODEL)
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
            logger.warning(
                "context_truncated",
                original_length=len(context),
                max_length=settings.MAX_CONTEXT_LENGTH,
            )
            context = context[: settings.MAX_CONTEXT_LENGTH] + "..."

        return context

    # --------------------------------------------------
    # System prompt (MOST IMPORTANT)
    # --------------------------------------------------
    def _build_system_prompt(self) -> str:
        return """
You are an Indian Legal Assistant specializing in the Indian Penal Code (IPC).

YOU MUST FOLLOW THIS OUTPUT FORMAT STRICTLY:

--------------------------------
RELEVANT PROVISIONS:
- Section XXX: Title
- Section YYY: Title

ANALYSIS:
- Bullet point explanation
- One legal idea per bullet
- Explicitly mention IPC section numbers
- Clear and professional tone

PUNISHMENT (if applicable):
- State punishment clearly
- Mention exact IPC section

IMPORTANT RULES:
- DO NOT write long paragraphs
- DO NOT invent IPC sections
- DO NOT hallucinate punishments
- If context is insufficient, clearly say so
- Prefer bullets over prose
--------------------------------

Write like a legal reference, not a chatbot.
"""

    # --------------------------------------------------
    # User prompt
    # --------------------------------------------------
    def _build_user_prompt(self, query: str, context: str) -> str:
        return f"""
IPC CONTEXT:
{context}

USER QUESTION:
{query}

Answer strictly based on the IPC context above.
"""

    # --------------------------------------------------
    # Main generation
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
                {"role": "system", "content": self._build_system_prompt()}
            ]

            # Keep chat history minimal (last few turns only)
            if chat_history:
                messages.extend(chat_history[-4:])

            messages.append(
                {"role": "user", "content": self._build_user_prompt(query, context)}
            )

            logger.info(
                "generating_answer",
                query=query[:60],
                has_history=bool(chat_history),
                context_length=len(context),
            )

            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=0.2,   # lower = more factual
                max_tokens=900,
            )

            answer = response.choices[0].message.content.strip()

            logger.info(
                "answer_generated",
                answer_length=len(answer),
                model=settings.LLM_MODEL,
            )

            return answer

        except Exception as e:
            logger.error("llm_generation_failed", error=str(e))
            raise LLMError(f"Failed to generate answer: {e}")


# --------------------------------------------------
# Singleton
# --------------------------------------------------
_llm_chain: Optional[LLMChain] = None


def get_llm_chain() -> LLMChain:
    global _llm_chain
    if _llm_chain is None:
        _llm_chain = LLMChain()
    return _llm_chain
"""
LLM chain for generating answers using Groq.

Optimized for legal correctness + readability:
- Bullet points
- Section consolidation
- Clear punishments
- No wall-of-text answers
"""

from typing import List, Dict, Optional
from groq import Groq

from app.config import settings
from app.utils import get_logger, LLMError
from app.models import RetrievedDocument

logger = get_logger(__name__)


class LLMChain:
    """Orchestrates LLM calls for IPC-based legal answers."""

    def __init__(self):
        try:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
            logger.info("llm_chain_initialized", model=settings.LLM_MODEL)
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
            logger.warning(
                "context_truncated",
                original_length=len(context),
                max_length=settings.MAX_CONTEXT_LENGTH,
            )
            context = context[: settings.MAX_CONTEXT_LENGTH] + "..."

        return context

    # --------------------------------------------------
    # SYSTEM PROMPT (CRITICAL LOGIC LAYER)
    # --------------------------------------------------
    def _build_system_prompt(self) -> str:
        return """
You are an Indian Legal Assistant specializing in the Indian Penal Code (IPC).

LEGAL REASONING RULES (STRICT):

1. IPC offences may be defined across MULTIPLE related sections.
   - A parent section defines the offence (e.g., Section 376 – Rape)
   - Sub-sections or related sections define punishment and aggravations
     (e.g., Sections 376A, 376AB, 376D, 376DA, 376DB)

2. If the parent section does not fully specify punishment:
   - You MUST identify and use related punishment sections
   - You MUST consolidate them into a single legal answer
   - You MUST NOT say "punishment not specified" if such sections exist

3. NEVER invent IPC sections or punishments.
4. NEVER guess beyond the provided context.
5. If and ONLY IF no relevant punishment sections exist, say so clearly.

--------------------------------
MANDATORY OUTPUT FORMAT:
--------------------------------

RELEVANT PROVISIONS:
- Section XXX: Title
- Section YYY: Title

ANALYSIS:
- Bullet points only
- One legal idea per bullet
- Explicit IPC section references
- Clear legal reasoning

PUNISHMENT (if applicable):
- Bullet points
- Mention exact IPC section
- Mention minimum / maximum punishment if stated

IMPORTANT NOTES:
- Conditions
- Exceptions
- Legal scope

--------------------------------
Write like a legal reference, not a chatbot.
"""

    # --------------------------------------------------
    # USER PROMPT
    # --------------------------------------------------
    def _build_user_prompt(self, query: str, context: str) -> str:
        return f"""
IPC CONTEXT (may contain multiple related sections):
{context}

USER QUESTION:
{query}

TASK:
- Identify the main offence
- Identify all related punishment sections
- Provide a consolidated legal answer
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
                {"role": "system", "content": self._build_system_prompt()}
            ]

            # Keep minimal conversational memory
            if chat_history:
                messages.extend(chat_history[-4:])

            messages.append(
                {"role": "user", "content": self._build_user_prompt(query, context)}
            )

            logger.info(
                "generating_answer",
                query=query[:60],
                has_history=bool(chat_history),
                context_length=len(context),
            )

            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=900,
            )

            answer = response.choices[0].message.content.strip()

            logger.info(
                "answer_generated",
                answer_length=len(answer),
                model=settings.LLM_MODEL,
            )

            return answer

        except Exception as e:
            logger.error("llm_generation_failed", error=str(e))
            raise LLMError(f"Failed to generate answer: {e}")


# --------------------------------------------------
# Singleton
# --------------------------------------------------
_llm_chain: Optional[LLMChain] = None


def get_llm_chain() -> LLMChain:
    global _llm_chain
    if _llm_chain is None:
        _llm_chain = LLMChain()
    return _llm_chain
