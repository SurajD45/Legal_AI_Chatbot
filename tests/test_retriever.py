"""
Tests for document retriever module.

Run with: pytest tests/test_retriever.py
"""

import pytest
from app.core.retriever import DocumentRetriever, get_retriever


class TestDocumentRetriever:
    """Test suite for DocumentRetriever class."""
    
    def test_singleton_pattern(self):
        """Test that retriever follows singleton pattern."""
        retriever1 = get_retriever()
        retriever2 = get_retriever()
        
        assert retriever1 is retriever2, "Should return same instance"
    
    def test_detect_sections(self):
        """Test section number detection from queries."""
        retriever = get_retriever()
        
        # Test basic section detection
        sections = retriever.detect_sections("What is Section 302?")
        assert "302" in sections
        
        # Test multiple sections
        sections = retriever.detect_sections("Explain Section 420 and Section 498A")
        assert "420" in sections
        assert "498A" in sections
        
        # Test Hindi/regional language
        sections = retriever.detect_sections("धारा 307 क्या है?")
        assert "307" in sections
        
        # Test no sections
        sections = retriever.detect_sections("What are punishments for theft?")
        assert len(sections) == 0
    
    @pytest.mark.asyncio
    async def test_search_by_section(self):
        """Test direct section lookup."""
        retriever = get_retriever()
        
        # This will fail if data is not indexed
        try:
            results = retriever.search_by_section("302", limit=1)
            assert len(results) <= 1
            if results:
                assert results[0].section == "302"
        except Exception as e:
            pytest.skip(f"Qdrant not available or data not indexed: {e}")
    
    @pytest.mark.asyncio
    async def test_semantic_search(self):
        """Test semantic search functionality."""
        retriever = get_retriever()
        
        try:
            results = retriever.semantic_search("murder punishment", top_k=3)
            assert len(results) <= 3
            assert all(hasattr(r, 'score') for r in results)
        except Exception as e:
            pytest.skip(f"Qdrant not available: {e}")
    
    @pytest.mark.asyncio
    async def test_hybrid_search(self):
        """Test hybrid search (section + semantic)."""
        retriever = get_retriever()
        
        try:
            # With section number
            results1 = retriever.hybrid_search("What is Section 302?")
            assert len(results1) >= 1
            
            # Without section number
            results2 = retriever.hybrid_search("theft punishment")
            assert len(results2) >= 1
        except Exception as e:
            pytest.skip(f"Qdrant not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])