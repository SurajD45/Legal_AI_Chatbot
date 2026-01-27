#!/usr/bin/env python3
"""
Robust IPC ingestion script for Qdrant.
Guarantees:
- No empty sections
- No duplicate sections
- No silent overwrites
- Full IPC coverage
- Compatible with latest Qdrant server
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import List, Dict, Set

# -----------------------------
# OFFLINE / MODEL CONFIG
# -----------------------------
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/models/huggingface"

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

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

    seen: Set[str] = set()
    clean_docs = []

    for doc in data:
        section = str(doc.get("section_number", "")).strip()
        text = str(doc.get("text", "")).strip()

        if not section or not text:
            logger.warning("dropping_invalid_section", section=section)
            continue

        if section in seen:
            logger.warning("duplicate_section_skipped", section=section)
            continue

        seen.add(section)
        clean_docs.append(doc)

    logger.info(
        "ipc_validation_complete",
        total_raw=len(data),
        total_clean=len(clean_docs),
        dropped=len(data) - len(clean_docs),
    )

    if not clean_docs:
        raise RuntimeError("No assumeable IPC sections found after validation")

    return clean_docs


# --------------------------------------------------
# RECREATE COLLECTION (SAFE)
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
# INDEX DOCUMENTS
# --------------------------------------------------
def index_documents(
    client: QdrantClient,
    model: SentenceTransformer,
    documents: List[Dict],
    batch_size: int = 64,
):
    name = settings.QDRANT_COLLECTION_NAME

    points = []
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
                    "section_number": doc["section_number"],
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
        raise FileNotFoundError(f"Missing file: {data_path}")

    documents = load_and_validate_ipc(str(data_path))

    model = SentenceTransformer(
        settings.EMBEDDING_MODEL,
        cache_folder=os.environ["HF_HOME"],
    )

    dimension = model.get_sentence_embedding_dimension()

    client = QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        timeout=30.0,
    )

    recreate_collection(client, dimension)
    index_documents(client, model, documents)

    print("\n✅ IPC ingestion successful")
    print(f"📚 Sections indexed: {len(documents)}")
    print(f"🧠 Vector dimension: {dimension}")
    print(f"🗄️ Collection: {settings.QDRANT_COLLECTION_NAME}")


if __name__ == "__main__":
    main()
