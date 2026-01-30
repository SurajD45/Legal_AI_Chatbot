#!/usr/bin/env python3
"""
IPC ingestion script for Qdrant Cloud.

Guarantees:
- No empty sections
- No duplicate sections
- Safe re-creation of collection
- Cloud-compatible (QDRANT_URL + API KEY)
- Payload index for section-based filtering (REQUIRED for Qdrant Cloud)
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import List, Dict, Set

# -----------------------------
# MODEL / HF CONFIG
# -----------------------------
os.environ.setdefault("HF_HOME", "/models/huggingface")

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PayloadSchemaType,
)
from tqdm import tqdm

# project imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# --------------------------------------------------
# LOAD + VALIDATE IPC DATA
# --------------------------------------------------
def load_and_validate_ipc(file_path: str) -> List[Dict]:
    logger.info("loading_ipc_json", path=file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    seen_sections: Set[str] = set()
    clean_docs: List[Dict] = []

    for doc in data:
        section = str(doc.get("section_number", "")).strip()
        text = str(doc.get("text", "")).strip()

        if not section or not text:
            logger.warning("dropping_invalid_section", section=section)
            continue

        if section in seen_sections:
            logger.warning("duplicate_section_skipped", section=section)
            continue

        seen_sections.add(section)
        clean_docs.append(doc)

    logger.info(
        "ipc_validation_complete",
        total_raw=len(data),
        total_clean=len(clean_docs),
        dropped=len(data) - len(clean_docs),
    )

    if not clean_docs:
        raise RuntimeError("No valid IPC sections found after validation")

    return clean_docs


# --------------------------------------------------
# RECREATE COLLECTION
# --------------------------------------------------
def recreate_collection(client: QdrantClient, dimension: int):
    name = settings.QDRANT_COLLECTION_NAME

    try:
        client.delete_collection(name)
        logger.info("deleted_existing_collection", collection=name)
    except Exception:
        logger.info("collection_not_present", collection=name)

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=dimension,
            distance=Distance.COSINE,
        ),
    )

    logger.info("collection_created", collection=name, dimension=dimension)


# --------------------------------------------------
# CREATE PAYLOAD INDEX (🔥 CRITICAL FOR CLOUD 🔥)
# --------------------------------------------------
def create_payload_indexes(client: QdrantClient):
    name = settings.QDRANT_COLLECTION_NAME

    client.create_payload_index(
        collection_name=name,
        field_name="section_number",
        field_schema=PayloadSchemaType.KEYWORD,
    )

    logger.info(
        "payload_index_created",
        collection=name,
        field="section_number",
    )


# --------------------------------------------------
# INDEX DOCUMENTS
# --------------------------------------------------
def index_documents(
    client: QdrantClient,
    model: SentenceTransformer,
    documents: List[Dict],
    batch_size: int = 64,
):
    name = settings.QDRANT_COLLECTION_NAME
    points: List[PointStruct] = []
    indexed = 0

    for doc in tqdm(documents, desc="Indexing IPC sections"):
        embed_text = f"{doc.get('title','')} {doc.get('text','')}".strip()

        vector = model.encode(
            embed_text,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "section_number": str(doc["section_number"]),
                    "title": doc.get("title"),
                    "chapter": doc.get("chapter"),
                    "chapter_title": doc.get("chapter_title"),
                    "text": doc.get("text"),
                    "source": doc.get("source"),
                },
            )
        )

        if len(points) >= batch_size:
            client.upsert(collection_name=name, points=points)
            indexed += len(points)
            points.clear()

    if points:
        client.upsert(collection_name=name, points=points)
        indexed += len(points)

    logger.info(
        "indexing_complete",
        expected=len(documents),
        indexed=indexed,
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    logger.info("ipc_ingestion_started")

    data_path = Path(__file__).parent.parent / "data" / "ipc_clean.json"
    if not data_path.exists():
        raise FileNotFoundError(f"Missing IPC data file: {data_path}")

    documents = load_and_validate_ipc(str(data_path))

    model = SentenceTransformer(
        settings.EMBEDDING_MODEL,
        cache_folder=os.environ["HF_HOME"],
    )
    dimension = model.get_sentence_embedding_dimension()

    client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        timeout=30.0,
    )

    recreate_collection(client, dimension)
    create_payload_indexes(client)     # 🔥 REQUIRED
    index_documents(client, model, documents)

    print("\n✅ IPC ingestion successful")
    print(f"📚 Sections indexed: {len(documents)}")
    print(f"🧠 Vector dimension: {dimension}")
    print(f"🗄️ Collection: {settings.QDRANT_COLLECTION_NAME}")


if __name__ == "__main__":
    main()
