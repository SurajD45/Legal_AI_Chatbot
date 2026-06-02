"""
LLM Judge for Answer Quality Evaluation using Groq API.
Evaluates Faithfulness, Groundedness, Completeness, and Consistency.
"""

import json
import time
from typing import Dict, Any, List
from groq import Groq
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)


class LLMJudge:
    def __init__(self):
        self._init_api_keys()
        self.client = Groq(api_key=self.api_keys[self.current_key_idx], max_retries=0)
        self.model = settings.LLM_MODEL
        logger.info("llm_judge_initialized", model=self.model, num_keys=len(self.api_keys))

    def _init_api_keys(self):
        self.api_keys = []
        if getattr(settings, "GROQ_API_KEY", None):
            self.api_keys.append(settings.GROQ_API_KEY)
        for idx in range(2, 10):
            val = getattr(settings, f"GROQ_API_KEY_{idx}", None)
            if val and val not in self.api_keys:
                self.api_keys.append(val)
        if not self.api_keys:
            self.api_keys.append(settings.GROQ_API_KEY)
        self.current_key_idx = 0

    def _rotate_key(self):
        if len(self.api_keys) > 1:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            self.client = Groq(api_key=self.api_keys[self.current_key_idx], max_retries=0)
            logger.info("llm_judge_key_rotated", new_key_index=self.current_key_idx)

    def evaluate_answer(
        self,
        query: str,
        context: str,
        answer: str,
    ) -> Dict[str, Any]:
        """Evaluate a generated answer against the query and retrieved context."""
        
        system_prompt = """You are an Indian Legal Evaluator. Evaluate the generated legal answer against the retrieved IPC context and the user query on 5 dimensions.
Do NOT use chain-of-thought or reasoning blocks. Provide ONLY a JSON object containing a score (0.0 to 1.0) and a concise sentence of evidence for each metric.

JSON Schema:
{
  "faithfulness": {
    "score": float,
    "evidence": "concise evidence sentence"
  },
  "groundedness": {
    "score": float,
    "evidence": "concise evidence sentence"
  },
  "completeness": {
    "score": float,
    "evidence": "concise evidence sentence"
  },
  "consistency": {
    "score": float,
    "evidence": "concise evidence sentence"
  },
  "scope_handling": {
    "score": float,
    "evidence": "concise evidence sentence"
  }
}

Definitions:
- faithfulness: Are the claims in the answer supported by the context without hallucination? (1.0 = fully supported, 0.0 = contains major unsupported claims or contradictions).
- groundedness: Is the answer derived strictly from the context, or does it include external filler/knowledge? (1.0 = strictly grounded, 0.0 = ignores context).
- completeness: Does the answer fully resolve all parts of the user query based on the context? (1.0 = fully answers query, 0.0 = fails to answer).
- consistency: How well does the answer align with and represent the retrieved context? (1.0 = highly consistent, 0.0 = inconsistent).
- scope_handling: Does the assistant correctly handle the query's scope? (For out-of-scope queries like tax returns, GST, general procedures, etc., does it identify them as out-of-scope and politely decline using the Out-of-Scope Notice? For in-scope IPC queries, does it answer normally and avoid falsely claiming it is out of scope? 1.0 = correct scope handling, 0.0 = incorrect).
"""

        user_prompt = f"""USER QUERY: {query}

RETRIEVED IPC CONTEXT:
{context}

GENERATED ANSWER:
{answer}

Output the JSON evaluation:"""

        # Retry loop for rate limits or transient errors
        max_attempts = max(5, len(self.api_keys) * 2)
        last_err = None
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=self.model,
                    temperature=0.0,  # Max determinism
                    response_format={"type": "json_object"},
                    max_tokens=800,
                )
                raw_content = response.choices[0].message.content
                return json.loads(raw_content)
            except Exception as e:
                last_err = e
                err_msg = str(e).upper()
                import groq
                is_rate_limit = isinstance(e, groq.RateLimitError) or "429" in err_msg or "RATE_LIMIT" in err_msg or "TOO MANY REQUESTS" in err_msg or "LIMIT" in err_msg
                is_overloaded = "503" in err_msg or "OVERLOADED" in err_msg or "SERVICE_UNAVAILABLE" in err_msg or "500" in err_msg

                if (is_rate_limit or is_overloaded) and len(self.api_keys) > 1:
                    logger.warning("llm_judge_rate_limited_rotating_key", error=str(e), attempt=attempt)
                    self._rotate_key()
                    time.sleep(3.0)
                else:
                    if attempt < max_attempts - 1:
                        sleep_time = 2.0 * (attempt + 1)
                        logger.warning("llm_judge_retry", attempt=attempt+1, error=str(e), sleep_time=sleep_time)
                        time.sleep(sleep_time)
                    else:
                        logger.error("llm_judge_failed", error=str(e))
                        break

        # Fallback return if we exited the loop without returning a successful response
        logger.error("llm_judge_failed_all_attempts", error=str(last_err))
        return {
            "faithfulness": {"score": 0.0, "evidence": f"Evaluation error: {last_err}"},
            "groundedness": {"score": 0.0, "evidence": f"Evaluation error: {last_err}"},
            "completeness": {"score": 0.0, "evidence": f"Evaluation error: {last_err}"},
            "consistency": {"score": 0.0, "evidence": f"Evaluation error: {last_err}"},
            "scope_handling": {"score": 0.0, "evidence": f"Evaluation error: {last_err}"}
        }
