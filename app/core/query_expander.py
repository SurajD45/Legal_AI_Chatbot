"""
Static query expansion for legal vocabulary normalization.

No external API calls. Fully deterministic.
Dictionary loaded from external JSON at startup.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set

from app.utils import get_logger

logger = get_logger(__name__)

# --------------------------------------------------
# Load dictionary from external JSON
# --------------------------------------------------
_DATA_PATH = Path(__file__).parent.parent / "data" / "query_expansion.json"


def _load_dictionary() -> Dict[str, Dict[str, List[str]]]:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_DICT = _load_dictionary()
VOCABULARY_MAP: Dict[str, List[str]] = _DICT["vocabulary_map"]
SYNONYM_MAP: Dict[str, List[str]] = _DICT["synonym_map"]
LEGAL_CONCEPT_MAP: Dict[str, List[str]] = _DICT["legal_concept_map"]

logger.info(
    "query_expansion_dictionary_loaded",
    vocabulary_entries=len(VOCABULARY_MAP),
    synonym_entries=len(SYNONYM_MAP),
    legal_concept_entries=len(LEGAL_CONCEPT_MAP),
)

# Precompute merged map and sorted multi-word phrases (longest first)
_ALL_MAPS: Dict[str, List[str]] = {**VOCABULARY_MAP, **SYNONYM_MAP}
_MULTI_WORD_PHRASES = sorted(
    [k for k in _ALL_MAPS if " " in k],
    key=lambda x: len(x),
    reverse=True,
)


# --------------------------------------------------
# Public API
# --------------------------------------------------
def expand_query_with_trace(query: str) -> tuple[str, list[str]]:
    """Expand query with legal synonyms and Hinglish translations, returning the matched rules trace.

    The expansion is additive — original query tokens are always preserved.
    Returns (original_query, []) if no dictionary keys match.
    """
    lower_q = query.lower()
    expansions: Set[str] = set()
    trace: List[str] = []

    # Phase 1: Multi-word phrase matching (greedy, longest first)
    for phrase in _MULTI_WORD_PHRASES:
        if phrase in lower_q:
            terms = _ALL_MAPS.get(phrase, [])
            if terms:
                expansions.update(terms)
                trace.append(f"{phrase} -> {','.join(terms)}")

    # Phase 2: Single-word token matching
    tokens = re.findall(r"[a-z0-9]+", lower_q)
    for token in tokens:
        if token in VOCABULARY_MAP:
            terms = VOCABULARY_MAP[token]
            if terms:
                expansions.update(terms)
                trace.append(f"{token} -> {','.join(terms)}")
        if token in SYNONYM_MAP:
            terms = SYNONYM_MAP[token]
            if terms:
                expansions.update(terms)
                trace.append(f"{token} -> {','.join(terms)}")

    # Phase 3: Concept expansion on collected terms + original tokens
    for term in list(expansions) + tokens:
        if term in LEGAL_CONCEPT_MAP:
            terms = LEGAL_CONCEPT_MAP[term]
            if terms:
                expansions.update(terms)
                trace.append(f"{term} -> {','.join(terms)}")

    # Remove empty strings
    expansions.discard("")

    # Deduplicate trace entries while preserving order
    seen_trace = set()
    deduped_trace = []
    for t in trace:
        if t not in seen_trace:
            seen_trace.add(t)
            deduped_trace.append(t)

    if not expansions:
        logger.info(
            "query_expansion", original=query, expanded=query, expanded_terms=0
        )
        return query, deduped_trace

    # Deduplicate against existing query tokens
    existing_tokens = set(tokens)
    new_terms = sorted(t for t in expansions if t.lower() not in existing_tokens)

    if not new_terms:
        logger.info(
            "query_expansion", original=query, expanded=query, expanded_terms=0
        )
        return query, deduped_trace

    expanded = f"{query} {' '.join(new_terms)}"
    logger.info(
        "query_expansion",
        original=query,
        expanded=expanded,
        expanded_terms=len(new_terms),
    )
    return expanded, deduped_trace


def expand_query(query: str) -> str:
    """Wrapper around expand_query_with_trace that discards the trace.

    Maintains backward compatibility with the rest of the codebase.
    """
    expanded, _ = expand_query_with_trace(query)
    return expanded
