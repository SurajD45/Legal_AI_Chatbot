"""
Context Expander — Phase 9B

Expands retrieved documents with semantically related IPC sections
using a curated mapping file (data/related_sections.json).

Pipeline position:
    Retrieved Documents
        │
        ▼
    [Context Expander]   ← loads related_sections.json
        │
        ▼
    Expanded Documents ──► LLM Chain

Design decisions:
- Fully decoupled from both the retriever and LLM chain.
- Related sections loaded from ipc_by_section (BM25 in-memory cache in retriever).
- Prevents duplicate sections — already-retrieved sections are not re-added.
- Expanded docs are tagged with source="expansion" for observability.
- Falls back gracefully if a related section is not in the BM25 index.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set

from app.models import RetrievedDocument
from app.utils import get_logger

logger = get_logger(__name__)

_RELATED_SECTIONS_PATH = (
    Path(__file__).parent.parent.parent / "data" / "related_sections.json"
)

# Score assigned to expanded (related) sections — slightly below primary results
_EXPANSION_SCORE = 0.85


class ContextExpander:
    """Expands a list of retrieved documents with related IPC sections."""

    def __init__(self, ipc_by_section: Dict[str, dict]):
        """
        Args:
            ipc_by_section: The in-memory section lookup dict from DocumentRetriever.
                            Keys are string section numbers, values are raw dicts
                            with 'title', 'text', 'section_number' fields.
        """
        self.ipc_by_section = ipc_by_section
        self.section_map = self._load_section_map()
        logger.info(
            "context_expander_initialized",
            mapped_sections=len(self.section_map),
        )

    def _load_section_map(self) -> Dict[str, List[str]]:
        """Loads the related sections mapping from JSON."""
        try:
            with open(_RELATED_SECTIONS_PATH, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            logger.info(
                "related_sections_loaded",
                path=str(_RELATED_SECTIONS_PATH),
                entries=len(mapping),
            )
            return mapping
        except Exception as e:
            logger.error("related_sections_load_failed", error=str(e))
            return {}

    def expand(
        self, documents: List[RetrievedDocument]
    ) -> List[RetrievedDocument]:
        """
        Expand the retrieved document list with related IPC sections.

        Args:
            documents: Primary retrieved documents from the retriever.

        Returns:
            Original documents + any newly discovered related sections,
            deduplicated. Primary documents always come first.
        """
        if not documents:
            return documents

        # Track which sections are already in the result set
        already_retrieved: Set[str] = {str(doc.section) for doc in documents}
        expanded_docs: List[RetrievedDocument] = list(documents)
        added_sections: List[str] = []

        for doc in documents:
            section_key = str(doc.section)
            related = self.section_map.get(section_key, [])

            for related_sec in related:
                related_sec_str = str(related_sec)

                # Skip if already in result set
                if related_sec_str in already_retrieved:
                    continue

                # Fetch from in-memory BM25 index
                raw = self.ipc_by_section.get(related_sec_str)
                if raw is None:
                    logger.warning(
                        "expansion_section_not_found",
                        section=related_sec_str,
                        triggered_by=section_key,
                    )
                    continue

                expanded_docs.append(
                    RetrievedDocument(
                        section=related_sec_str,
                        title=raw.get("title", ""),
                        text=raw.get("text", ""),
                        score=_EXPANSION_SCORE,
                    )
                )
                already_retrieved.add(related_sec_str)
                added_sections.append(related_sec_str)

        if added_sections:
            logger.info(
                "context_expanded",
                original_count=len(documents),
                expanded_count=len(expanded_docs),
                added_sections=added_sections,
            )
        else:
            logger.info(
                "context_expansion_no_additions",
                section_count=len(documents),
            )

        return expanded_docs


# ---------------------------------------------------------------------------
# Singleton factory — requires retriever's ipc_by_section at first init
# ---------------------------------------------------------------------------
_expander: Optional[ContextExpander] = None


def get_context_expander() -> ContextExpander:
    """
    Returns the singleton ContextExpander.
    Must be called AFTER the DocumentRetriever has been initialized
    (so ipc_by_section is already populated in memory).
    """
    global _expander
    if _expander is None:
        from app.core.retriever import get_retriever
        retriever = get_retriever()
        _expander = ContextExpander(ipc_by_section=retriever.ipc_by_section)
    return _expander
