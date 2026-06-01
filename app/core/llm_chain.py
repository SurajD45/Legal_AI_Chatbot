"""
LLM chain for generating answers using Groq API.
Uses the official Groq SDK with LPU-accelerated inference.
"""

from typing import List, Dict, Optional
import traceback

from groq import Groq

from app.config import settings
from app.utils import get_logger, LLMError
from app.models import RetrievedDocument

logger = get_logger(__name__)


class LLMChain:
    """Orchestrates Groq LLM calls for IPC-based legal answers."""

    def __init__(self):
        try:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
            self.model = settings.LLM_MODEL

            logger.info("llm_chain_initialized", model=self.model, provider="groq")

        except Exception as e:
            logger.error("llm_init_failed", error=str(e))
            raise LLMError(f"Failed to initialize LLM: {e}")

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

    def _build_system_prompt(self) -> str:
        return """You are an Indian Legal Assistant specializing in the Indian Penal Code (IPC).

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
- Mention IPC section"""

    def _build_user_prompt(self, query: str, context: str) -> str:
        return f"""IPC CONTEXT:
{context}

QUESTION:
{query}"""

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
            ]

            if chat_history:
                # Use a sliding window of the last 8 messages (4 turns) to prevent context bloat
                recent_history = chat_history[-8:]
                for msg in recent_history:
                    messages.append({"role": msg["role"], "content": msg["content"]})

            messages.append(
                {"role": "user", "content": self._build_user_prompt(query, context)}
            )

            logger.info(
                "calling_groq",
                model=self.model,
                context_length=len(context),
            )

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=1024,
            )

            answer = completion.choices[0].message.content.strip()

            usage = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens,
            }
            logger.info("groq_success", tokens_used=usage)

            return answer

        except Exception as e:
            logger.error(
                "groq_call_failed",
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
            )
            raise LLMError(f"Failed to generate answer: {e}")


_llm_chain: Optional[LLMChain] = None


def get_llm_chain() -> LLMChain:
    global _llm_chain
    if _llm_chain is None:
        _llm_chain = LLMChain()
    return _llm_chain