"""
LLM chain for generating answers using OpenRouter.
Production-safe version (Railway compatible).
"""

from typing import List, Dict, Optional
import traceback
import httpx

from app.config import settings
from app.utils import get_logger, LLMError
from app.models import RetrievedDocument

logger = get_logger(__name__)


class LLMChain:
    """Orchestrates LLM calls for IPC-based legal answers."""

    def __init__(self):
        try:
            self.api_key = settings.OPENROUTER_API_KEY
            self.model = settings.LLM_MODEL
            self.base_url = "https://openrouter.ai/api/v1"
            
            logger.info("llm_chain_initialized", model=self.model, provider="openrouter")

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
                {"role": "user", "content": self._build_user_prompt(query, context)},
            ]

            logger.info(
                "calling_openrouter",
                model=self.model,
                context_length=len(context),
            )

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://legalaichatbot-production.up.railway.app",
                "X-Title": "Legal AI Assistant",
            }

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 700,
            }

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            answer = data["choices"][0]["message"]["content"].strip()
            logger.info("openrouter_success", tokens_used=data.get("usage", {}))
            
            return answer

        except httpx.HTTPStatusError as e:
            logger.error(
                "openrouter_http_error",
                status_code=e.response.status_code,
                error=e.response.text[:500],
                traceback=traceback.format_exc(),
            )
            raise LLMError(f"OpenRouter API error: {e.response.status_code}")

        except Exception as e:
            logger.error(
                "openrouter_call_failed",
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