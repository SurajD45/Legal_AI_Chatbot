"""
Query Condenser — Phase 9A

Converts ambiguous follow-up queries into self-contained standalone questions
by fusing them with chat history context.

Pipeline position:
    User Query
        │
        ▼
    [Keyword Filter]  ── (no match) ──► original query (0ms overhead)
        │
        ▼ (match)
    [LLM Rephraser — llama-3.1-8b-instant]
        │
        ▼
    Standalone Search Query ──► Retriever

Design decisions:
- Keyword filter is regex-based, 0ms latency for standalone queries.
- Only contextual follow-ups trigger an LLM rephrase.
- Uses llama-3.1-8b-instant for speed (<200ms typical latency).
- Logs original vs rewritten query for debugging retrieval failures.
- Uses same Groq key rotation mechanism as LLMChain.
"""

import re
import time
import traceback
from typing import List, Dict, Optional

from groq import Groq

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Keyword Filter — triggers only for clearly contextual follow-ups
# ---------------------------------------------------------------------------
# These patterns indicate the user's query is a follow-up referencing a prior
# conversation turn. Standalone queries like "What is Section 420?" won't match.
_CONTEXTUAL_PATTERNS = re.compile(
    r"\b("
    r"definition|define|meaning|means|what is it|what does it mean"
    r"|punishment|punish|penalty|penalties|sentence|sentencing"
    r"|then|also|additionally|furthermore|moreover"
    r"|bailable|non.?bailable|cognizable|non.?cognizable|compoundable"
    r"|fine|amount|how much"
    r"|imprisonment|years|jail|prison"
    r"|ingredients|elements|essentials|components"
    r"|exceptions?|exception to|proviso"
    r"|examples?|illustration|case|cases"
    r"|this offence|that section|this section|that offence|it|its|this crime"
    r"|what about|tell me more|explain more|elaborate"
    r"|grievous|simple hurt|attempt|abetment"
    r")\b",
    re.IGNORECASE,
)

# Short queries (< 6 words) that look standalone should NOT be condensed
_SECTION_STANDALONE = re.compile(
    r"^(what is|explain|tell me about)\s+(section\s+)?\d+[A-Z]?\s*\??$",
    re.IGNORECASE,
)


def _is_contextual_query(query: str) -> bool:
    """Returns True only if the query looks like a contextual follow-up."""
    # If it explicitly mentions a new section number, treat as standalone
    if _SECTION_STANDALONE.match(query.strip()):
        return False
    return bool(_CONTEXTUAL_PATTERNS.search(query))


# ---------------------------------------------------------------------------
# Condenser prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """You are a query rewriting assistant for an Indian Penal Code (IPC) legal chatbot.

Your ONLY job: rewrite the user's follow-up question into a single, self-contained search query that can be understood without any prior conversation context.

Rules:
1. Output ONLY the rewritten query — no explanation, no preamble, no quotes.
2. Preserve all IPC section numbers, legal terms, and crime names from the conversation.
3. Make the query specific (include section number when relevant).
4. Do NOT add information not present in the conversation history.
5. If the query is already standalone, return it unchanged."""

_USER_TEMPLATE = """Conversation history:
{history}

Follow-up question: {query}

Rewritten standalone query:"""


# ---------------------------------------------------------------------------
# QueryCondenser class
# ---------------------------------------------------------------------------
class QueryCondenser:
    """Lightweight query rewriter using llama-3.1-8b-instant."""

    def __init__(self):
        self.model = "llama-3.1-8b-instant"
        self._init_api_keys()
        self.client = Groq(api_key=self.api_keys[self.current_key_idx], max_retries=0)
        logger.info(
            "query_condenser_initialized",
            model=self.model,
            num_keys=len(self.api_keys),
        )

    def _init_api_keys(self):
        self.api_keys = []
        if getattr(settings, "GROQ_API_KEY", None):
            self.api_keys.append(settings.GROQ_API_KEY)
        for idx in range(2, 10):
            val = getattr(settings, f"GROQ_API_KEY_{idx}", None)
            if val and val not in self.api_keys:
                self.api_keys.append(val)
        if not self.api_keys:
            raise RuntimeError("No Groq API keys available for QueryCondenser.")
        self.current_key_idx = 0

    def _rotate_key(self):
        if len(self.api_keys) > 1:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            self.client = Groq(
                api_key=self.api_keys[self.current_key_idx], max_retries=0
            )
            logger.info("condenser_key_rotated", new_key_index=self.current_key_idx)

    def _format_history(self, chat_history: List[Dict[str, str]]) -> str:
        """Formats the last 4 messages (2 turns) for the condenser prompt."""
        recent = chat_history[-4:]
        lines = []
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Assistant"
            # Truncate long assistant messages to prevent bloating condenser context
            content = msg["content"]
            if msg["role"] == "assistant" and len(content) > 300:
                content = content[:300] + "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def condense(
        self,
        query: str,
        chat_history: List[Dict[str, str]],
    ) -> Dict[str, str]:
        """
        Condenses a contextual follow-up query into a standalone search query.

        Returns a dict with:
            - search_query: the query to pass to the retriever
            - original_query: the raw user input
            - condensed: bool — whether condensation was applied
            - rewrite_ms: latency of the LLM call (0 if skipped)
        """
        # ── Step 1: Fast keyword filter ──────────────────────────────────────
        if not chat_history or not _is_contextual_query(query):
            logger.info(
                "condenser_skipped",
                query=query,
                reason="keyword_filter_no_match" if chat_history else "no_history",
            )
            return {
                "search_query": query,
                "original_query": query,
                "condensed": False,
                "rewrite_ms": 0,
            }

        # ── Step 2: LLM rephrase ─────────────────────────────────────────────
        history_text = self._format_history(chat_history)
        user_prompt = _USER_TEMPLATE.format(history=history_text, query=query)

        import groq as groq_lib

        t0 = time.perf_counter()
        completion = None
        last_err = None
        max_attempts = max(2, len(self.api_keys))

        for attempt in range(max_attempts):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=128,
                    tool_choice="none",
                )
                break
            except Exception as e:
                last_err = e
                err_msg = str(e).upper()
                is_rate_limit = (
                    isinstance(e, groq_lib.RateLimitError)
                    or "429" in err_msg
                    or "RATE_LIMIT" in err_msg
                )
                if is_rate_limit and len(self.api_keys) > 1:
                    self._rotate_key()
                    time.sleep(1.0)
                else:
                    logger.warning(
                        "condenser_error",
                        attempt=attempt,
                        error=str(e),
                        traceback=traceback.format_exc(),
                    )
                    break  # Fall back to original query on any non-rate-limit error

        rewrite_ms = int((time.perf_counter() - t0) * 1000)

        if completion is None:
            logger.error(
                "condenser_fallback",
                reason="all_attempts_failed",
                error=str(last_err),
                original_query=query,
            )
            return {
                "search_query": query,
                "original_query": query,
                "condensed": False,
                "rewrite_ms": rewrite_ms,
            }

        rewritten = completion.choices[0].message.content
        if not rewritten or not rewritten.strip():
            logger.warning("condenser_empty_response", original_query=query)
            rewritten = query

        rewritten = rewritten.strip().strip('"').strip("'")

        logger.info(
            "condenser_applied",
            original_query=query,
            rewritten_query=rewritten,
            rewrite_ms=rewrite_ms,
        )

        return {
            "search_query": rewritten,
            "original_query": query,
            "condensed": True,
            "rewrite_ms": rewrite_ms,
        }


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_condenser: Optional[QueryCondenser] = None


def get_query_condenser() -> QueryCondenser:
    global _condenser
    if _condenser is None:
        _condenser = QueryCondenser()
    return _condenser
