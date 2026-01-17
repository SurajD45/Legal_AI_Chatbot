import re
from typing import List, Optional
from functools import lru_cache

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.config import settings
from app.models import RetrievedDocument
from app.utils import get_logger

logger = get_logger(__name__)


class DocumentRetriever:
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self._model: Optional[SentenceTransformer] = None
        self._client: Optional[QdrantClient] = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("loading_embedding_model", model=settings.EMBEDDING_MODEL)
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return self._model

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            logger.info("connecting_qdrant")
            self._client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=10.0,
            )
        return self._client

    def detect_sections(self, query: str) -> List[str]:
        pattern = r"(?:section|sec\.?|u/s|धारा|कलम)\s*([0-9]+[A-Z]?)"
        return re.findall(pattern, query, flags=re.IGNORECASE)

    def search_by_section(self, section: str) -> List[RetrievedDocument]:
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="section_number",
                        match=MatchValue(value=section),
                    )
                ]
            ),
            limit=10,
            with_payload=True,
        )

        return [
            RetrievedDocument(
                section=p.payload.get("section_number"),
                title=p.payload.get("title"),
                text=p.payload.get("text"),
                score=1.0,
            )
            for p in results
        ]

    def semantic_search(self, query: str, top_k: int = 5) -> List[RetrievedDocument]:
        vector = self.model.encode(
            query[:1000],
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=top_k,
            with_payload=True,
        )

        return [
            RetrievedDocument(
                section=r.payload.get("section_number"),
                title=r.payload.get("title"),
                text=r.payload.get("text"),
                score=r.score,
            )
            for r in results
        ]

    def hybrid_search(self, query: str) -> List[RetrievedDocument]:
        sections = self.detect_sections(query)
        if sections:
            docs = []
            for sec in sections:
                docs.extend(self.search_by_section(sec))
            if docs:
                return docs
        return self.semantic_search(query)


@lru_cache
def get_retriever() -> DocumentRetriever:
    return DocumentRetriever()
