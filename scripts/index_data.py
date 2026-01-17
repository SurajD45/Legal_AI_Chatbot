#!/usr/bin/env python3
"""
Index IPC data into Qdrant vector database.

This script:
1. Loads IPC sections from JSON
2. Generates embeddings
3. Creates Qdrant collection
4. Uploads vectors with metadata

Run this once before starting the application.
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict

# CRITICAL: Set offline mode BEFORE importing sentence_transformers
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HOME'] = '/models/huggingface'

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def load_ipc_data(file_path: str) -> List[Dict]:
    """
    Load IPC data from JSON file.
    
    Args:
        file_path: Path to ipc.json
        
    Returns:
        List of IPC sections
    """
    logger.info("loading_ipc_data", path=file_path)
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
    
    logger.info("ipc_data_loaded", sections_count=len(data))
    return data


def create_collection(client: QdrantClient, dimension: int) -> None:
    """
    Create Qdrant collection for IPC data.
    
    Args:
        client: Qdrant client
        dimension: Embedding dimension
    """
    collection_name = settings.QDRANT_COLLECTION_NAME
    
    # Delete existing collection if it exists
    try:
        client.delete_collection(collection_name)
        logger.info("existing_collection_deleted", collection=collection_name)
    except Exception:
        pass  # Collection doesn't exist, that's fine
    
    # Create new collection
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=dimension,
            distance=Distance.COSINE
        )
    )
    
    logger.info("collection_created",
               collection=collection_name,
               dimension=dimension)


def index_documents(
    client: QdrantClient,
    model: SentenceTransformer,
    documents: List[Dict],
    batch_size: int = 100
) -> None:
    """
    Index documents into Qdrant.
    
    Args:
        client: Qdrant client
        model: Embedding model
        documents: IPC sections to index
        batch_size: Number of documents to process at once
    """
    collection_name = settings.QDRANT_COLLECTION_NAME
    
    logger.info("starting_indexing",
               total_docs=len(documents),
               batch_size=batch_size)
    
    points = []
    
    for idx, doc in enumerate(tqdm(documents, desc="Indexing documents")):
        # Create text to embed (combine title and content)
        section_num = str(doc.get("section", ""))
        title = doc.get("title", "")
        text = doc.get("text", "")
        
        # Skip empty documents
        if not text.strip():
            logger.warning("skipping_empty_document", section=section_num)
            continue
        
        # Create embedding text
        embed_text = f"{title} {text}".strip()
        
        # Generate embedding
        embedding = model.encode(
            embed_text,
            normalize_embeddings=True,
            show_progress_bar=False
        ).tolist()
        
        # Create point
        point = PointStruct(
            id=idx,
            vector=embedding,
            payload={
                "section_number": section_num,
                "title": title,
                "text": text
            }
        )
        
        points.append(point)
        
        # Upload batch
        if len(points) >= batch_size:
            client.upsert(
                collection_name=collection_name,
                points=points
            )
            logger.info("batch_uploaded", batch_size=len(points))
            points = []
    
    # Upload remaining points
    if points:
        client.upsert(
            collection_name=collection_name,
            points=points
        )
        logger.info("final_batch_uploaded", batch_size=len(points))
    
    # Get collection info
    collection_info = client.get_collection(collection_name)
    logger.info("indexing_complete",
               total_vectors=collection_info.vectors_count)


def main():
    """Main indexing function."""
    try:
        logger.info("indexing_started")
        
        # Load IPC data
        data_path = Path(__file__).parent.parent / "data" / "ipc.json"
        if not data_path.exists():
            logger.error("data_file_not_found", path=str(data_path))
            print(f"Error: Data file not found at {data_path}")
            print("Please ensure data/ipc.json exists")
            sys.exit(1)
        
        documents = load_ipc_data(str(data_path))
        
        # Load embedding model from cache
        logger.info("loading_embedding_model", model=settings.EMBEDDING_MODEL)

        # Try loading from local cache first
        cache_dir = os.environ.get('HF_HOME', '/models/huggingface')
        logger.info("using_cache_dir", cache_dir=cache_dir)

        # Load model - will download if not cached
        model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            cache_folder=cache_dir
        )
        
        dimension = model.get_sentence_embedding_dimension()
        logger.info("model_loaded", dimension=dimension)
        
        # Connect to Qdrant
        logger.info("connecting_to_qdrant",
                   host=settings.QDRANT_HOST,
                   port=settings.QDRANT_PORT)
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=30.0
        )
        
        # Create collection
        create_collection(client, dimension)
        
        # Index documents
        index_documents(client, model, documents)
        
        logger.info("indexing_successful")
        print("\n✅ Indexing completed successfully!")
        print(f"📊 Total sections indexed: {len(documents)}")
        print(f"🗄️  Collection: {settings.QDRANT_COLLECTION_NAME}")
        print(f"🚀 You can now start the application")
        
    except Exception as e:
        logger.error("indexing_failed", error=str(e))
        print(f"\n❌ Indexing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()