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
HINDI_LEGAL_MAP: Dict[str, List[str]] = _DICT["hindi_legal_map"]
ENGLISH_LEGAL_SYNONYMS: Dict[str, List[str]] = _DICT["english_legal_synonyms"]
CONCEPT_EXPANSION: Dict[str, List[str]] = _DICT["concept_expansion"]

logger.info(
    "query_expansion_dictionary_loaded",
    hindi_entries=len(HINDI_LEGAL_MAP),
    english_entries=len(ENGLISH_LEGAL_SYNONYMS),
    concept_entries=len(CONCEPT_EXPANSION),
)

# Precompute merged map and sorted multi-word phrases (longest first)
_ALL_MAPS: Dict[str, List[str]] = {**HINDI_LEGAL_MAP, **ENGLISH_LEGAL_SYNONYMS}
_MULTI_WORD_PHRASES = sorted(
    [k for k in _ALL_MAPS if " " in k],
    key=lambda x: len(x),
    reverse=True,
)


# --------------------------------------------------
# Public API
# --------------------------------------------------
def expand_query(query: str) -> str:
    """Expand query with legal synonyms and Hindi translations.

    The expansion is additive — original query tokens are always preserved.
    Returns the original query unchanged if no dictionary keys match.
    """
    lower_q = query.lower()
    expansions: Set[str] = set()

    # Phase 1: Multi-word phrase matching (greedy, longest first)
    for phrase in _MULTI_WORD_PHRASES:
        if phrase in lower_q:
            expansions.update(_ALL_MAPS.get(phrase, []))

    # Phase 2: Single-word token matching
    tokens = re.findall(r"[a-z0-9]+", lower_q)
    for token in tokens:
        if token in HINDI_LEGAL_MAP:
            expansions.update(HINDI_LEGAL_MAP[token])
        if token in ENGLISH_LEGAL_SYNONYMS:
            expansions.update(ENGLISH_LEGAL_SYNONYMS[token])

    # Phase 3: Concept expansion on collected terms + original tokens
    for term in list(expansions) + tokens:
        if term in CONCEPT_EXPANSION:
            expansions.update(CONCEPT_EXPANSION[term])

    # Remove empty strings
    expansions.discard("")

    if not expansions:
        logger.info(
            "query_expansion", original=query, expanded=query, expanded_terms=0
        )
        return query

    # Deduplicate against existing query tokens
    existing_tokens = set(tokens)
    new_terms = sorted(t for t in expansions if t.lower() not in existing_tokens)

    if not new_terms:
        logger.info(
            "query_expansion", original=query, expanded=query, expanded_terms=0
        )
        return query

    expanded = f"{query} {' '.join(new_terms)}"
    logger.info(
        "query_expansion",
        original=query,
        expanded=expanded,
        expanded_terms=len(new_terms),
    )
    return expanded
