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
            self._init_api_keys()
            self.client = Groq(api_key=self.api_keys[self.current_key_idx], max_retries=0)
            self.model = settings.LLM_MODEL
            self.last_token_usage = None

            logger.info("llm_chain_initialized", model=self.model, provider="groq", num_keys=len(self.api_keys))

        except Exception as e:
            logger.error("llm_init_failed", error=str(e))
            raise LLMError(f"Failed to initialize LLM: {e}")

    def _init_api_keys(self):
        self.api_keys = []
        if getattr(settings, "GROQ_API_KEY", None):
            self.api_keys.append(settings.GROQ_API_KEY)
        for idx in range(2, 10):
            val = getattr(settings, f"GROQ_API_KEY_{idx}", None)
            if val and val not in self.api_keys:
                self.api_keys.append(val)
        if not self.api_keys:
            raise LLMError("No Groq API keys found in settings.")
        self.current_key_idx = 0

    def _rotate_key(self):
        if len(self.api_keys) > 1:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            self.client = Groq(api_key=self.api_keys[self.current_key_idx], max_retries=0)
            logger.info("groq_key_rotated", new_key_index=self.current_key_idx)

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

SYSTEM RULES:
1. STRICT TRUTH & DETAIL RETENTION: Use ONLY the provided IPC context. Do not assume, extrapolate, or hallucinate.
   If present in the retrieved context, you MUST NEVER omit:
   - Fine amounts
   - Imprisonment duration
   - Classification details (e.g., cognizable/non-cognizable, bailable/non-bailable, compoundable)
   - Important exceptions
   - Relevant caveats
   All these details present in the retrieved context must appear in the answer.

2. CONDITIONAL STRUCTURED SECTIONS & MISSING CONTEXT HANDLING:
   - Your answer structure is conditional. Use only the relevant sections below when actual information exists in the retrieved context.
   - Do NOT generate filler content (e.g., "No information available", "Not provided", "N/A") or place empty headings/bullet points merely to satisfy a template. If information for a section is missing from the retrieved context, OMIT that section header and its content entirely from your response.
   - If the context contains a crime's definition but lacks its corresponding punishment section (or vice-versa), explain the part that is available normally, omit the missing section's header, do NOT hallucinate or assume the missing details, and list the missing context as an explicit notice in the `### LIMITATIONS` section.
     - Example: If definition exists but punishment is missing: omit the `### PUNISHMENT & PENALTIES` section entirely and add the limitation notice: "The retrieved context does not contain punishment details for this offense."
     - Example: If punishment exists but definition is missing: omit the `### DEFINITION & ELEMENTS` section entirely and add the limitation notice.

3. OUT-OF-SCOPE HANDLING:
   - If the query falls outside the IPC knowledge base (for example: GST, Income Tax, Passport, Banking, Government Schemes, or civil laws not defined under the IPC), you must immediately output the OUT OF SCOPE template below and explain the boundary.
   - Do NOT generate irrelevant IPC answers for out-of-scope queries.

FORMAT TEMPLATE (for in-scope queries):

### RELEVANT PROVISIONS
- [Section Number]
- [Title]

### DEFINITION & ELEMENTS (Include ONLY if definition/elements exist in the retrieved context. Otherwise, omit this section)
- [Essential ingredients of the offense]

### PUNISHMENT & PENALTIES (Include ONLY if punishment details exist in the retrieved context. Otherwise, omit this section)
- [Imprisonment]
- [Fine]
- [Additional consequences]

### CASE ANALYSIS (Include ONLY if retrieved sections apply to the user's specific scenario. Otherwise, omit this section)
- [Application of retrieved sections to user's scenario]

### LIMITATIONS (Always include this section)
- [Explicitly state missing information from retrieved context]
  Example: "The retrieved context does not contain punishment details for this offense." or "The retrieved context does not contain the definition for this offense."

OUT OF SCOPE TEMPLATE (Use EXACTLY this template when the query is out of scope / unrelated to the IPC):

### OUT OF SCOPE NOTICE

This query falls outside the IPC knowledge base.

### EXPLANATION

This assistant currently supports IPC-related criminal law queries only."""

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

            import time
            import groq

            completion = None
            last_err = None
            max_attempts = max(3, len(self.api_keys) * 2)

            for attempt in range(max_attempts):
                try:
                    completion = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.2,
                        max_tokens=1024,
                    )
                    break
                except Exception as e:
                    last_err = e
                    err_msg = str(e).upper()
                    is_rate_limit = isinstance(e, groq.RateLimitError) or "429" in err_msg or "RATE_LIMIT" in err_msg or "TOO MANY REQUESTS" in err_msg or "LIMIT" in err_msg
                    is_overloaded = "503" in err_msg or "OVERLOADED" in err_msg or "SERVICE_UNAVAILABLE" in err_msg or "500" in err_msg

                    if (is_rate_limit or is_overloaded) and len(self.api_keys) > 1:
                        logger.warning("groq_rate_limited_rotating_key", error=str(e), attempt=attempt)
                        self._rotate_key()
                        time.sleep(3.0)
                    else:
                        if attempt < max_attempts - 1:
                            sleep_time = 1.0 * (attempt + 1)
                            logger.warning("groq_error_retrying", error=str(e), attempt=attempt, sleep_time=sleep_time)
                            time.sleep(sleep_time)
                        else:
                            raise e

            if completion is None:
                raise last_err if last_err else LLMError("Failed to generate completion from Groq.")

            answer = completion.choices[0].message.content.strip()

            usage = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens,
            }
            self.last_token_usage = usage
            logger.info("groq_success", tokens_used=usage)

            return answer

        except Exception as e:
            self.last_token_usage = None
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