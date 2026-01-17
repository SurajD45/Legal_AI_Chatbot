#!/usr/bin/env python3
"""
Test retrieval system with sample queries.

This script allows you to test the hybrid search functionality
before deploying the full application.

Usage:
    python scripts/test_retrieval.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core import get_retriever
from app.utils import setup_logging, get_logger
from app.config import settings

setup_logging()
logger = get_logger(__name__)


def print_results(query: str, documents):
    """Pretty print retrieval results."""
    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"{'='*80}")

    if not documents:
        print("❌ No results found")
        return

    for i, doc in enumerate(documents, 1):
        print(f"\n[Result {i}]")
        print(f"Section: {doc.section}")
        print(f"Title: {doc.title}")
        print(f"Score: {doc.score:.4f}")
        print(f"Text: {doc.text[:200]}..." if len(doc.text) > 200 else f"Text: {doc.text}")


def test_section_detection():
    """Test section number detection."""
    print("\n" + "="*80)
    print("TEST 1: Section Detection")
    print("="*80)

    retriever = get_retriever()

    test_queries = [
        "What is Section 302?",
        "Explain Sec 420",
        "Tell me about Section 498A",
        "धारा 307",  # Hindi
    ]

    for query in test_queries:
        sections = retriever.detect_sections(query)
        print(f"Query: '{query}' → Detected sections: {sections}")


def test_hybrid_search():
    """Test hybrid search with various queries."""
    print("\n" + "="*80)
    print("TEST 2: Hybrid Search")
    print("="*80)

    retriever = get_retriever()

    # Test queries
    queries = [
        "What is Section 302?",  # Explicit section
        "What are the punishments for murder?",  # Semantic search
        "Tell me about theft laws",  # Semantic search
        "Section 420 punishment",  # Explicit section
        "Defamation in IPC",  # Semantic search
    ]

    for query in queries:
        try:
            documents = retriever.hybrid_search(query, top_k=3)
            print_results(query, documents)
        except Exception as e:
            print(f"\n❌ Error for query '{query}': {e}")


def test_semantic_search():
    """Test pure semantic search."""
    print("\n" + "="*80)
    print("TEST 3: Semantic Search")
    print("="*80)

    retriever = get_retriever()

    queries = [
        "Laws related to women safety",
        "Criminal breach of trust",
        "Punishment for assault",
    ]

    for query in queries:
        try:
            documents = retriever.semantic_search(query, top_k=5)
            print_results(query, documents)
        except Exception as e:
            print(f"\n❌ Error for query '{query}': {e}")


def main():
    """Run all tests."""
    try:
        print("\n🧪 Testing Legal AI Retrieval System")
        print(f"📊 Collection: {settings.QDRANT_COLLECTION_NAME}")
        print(f"🔗 Qdrant: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")

        # Run tests
        test_section_detection()
        test_hybrid_search()
        test_semantic_search()

        print("\n" + "="*80)
        print("✅ All tests completed!")
        print("="*80 + "\n")

    except Exception as e:
        logger.error("test_failed", error=str(e))
        print(f"\n❌ Test failed: {e}")
        print("\nMake sure:")
        print("1. Qdrant is running")
        print("2. Data has been indexed (run scripts/index_data.py)")
        print("3. Environment variables are set correctly")
        sys.exit(1)


if __name__ == "__main__":
    main()
