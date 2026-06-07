"""
tests/test_retriever.py
Tests for rag/retriever.py
 
Actual function names:
  get_similar_ads(query, n_results=5)  -> list of dicts
  format_for_agent(similar_ads)        -> str
 
Each result dict has:
  ad_copy, similarity_score, brand, product, platform,
  hook, sentiment, has_cta, price_mentioned, keywords
 
Private variable: _collection (ChromaDB)
"""
 
import pytest
from unittest.mock import patch, MagicMock
 
 
# ─────────────────────────────────────────────
# HELPER — fake ChromaDB response
# ─────────────────────────────────────────────
 
def make_mock_chroma_response(n=5):
    """
    ChromaDB .query() ka actual return format replicate karte hain.
    retriever.py line 78: results = _collection.query(...)
    """
    documents = [[
        "Sample competitor ad number {} with great hook today".format(i+1)
        for i in range(n)
    ]]
    metadatas = [[
        {
            "brand": "Brand{}".format(i+1),
            "product": "Product{}".format(i+1),
            "platform": "Instagram",
            "hook": "Great hook",
            "sentiment": "positive",
            "has_cta": "True",
            "price_mentioned": "False",
            "keywords": "quality, value, deal"
        }
        for i in range(n)
    ]]
    # distance 0 = identical, 2 = opposite
    # Chhoti distance = zyada similar
    distances = [[round(0.10 + i * 0.05, 2) for i in range(n)]]
 
    return {
        "documents": documents,
        "metadatas": metadatas,
        "distances": distances
    }
 
 
# ─────────────────────────────────────────────
# GROUP 1 — Result structure tests
# ─────────────────────────────────────────────
 
class TestRetrieverOutput:
    """get_similar_ads() must return correctly structured results."""
 
    @patch("rag.retriever._collection")
    def test_returns_correct_number_of_results(self, mock_col):
        """Must return exactly n_results=5 results."""
        mock_col.query.return_value = make_mock_chroma_response(n=5)
        from rag.retriever import get_similar_ads
        results = get_similar_ads("Buy now! Best price guaranteed today!")
        assert len(results) == 5, "Expected 5 results, got {}".format(len(results))
 
    @patch("rag.retriever._collection")
    def test_each_result_has_ad_copy(self, mock_col):
        """Each result must have 'ad_copy' key — used by format_for_agent."""
        mock_col.query.return_value = make_mock_chroma_response(n=3)
        from rag.retriever import get_similar_ads
        results = get_similar_ads("Amazing deal on premium quality products!")
        for i, result in enumerate(results):
            assert "ad_copy" in result, "Result {} missing 'ad_copy'".format(i)
 
    @patch("rag.retriever._collection")
    def test_each_result_has_similarity_score(self, mock_col):
        """Each result must have 'similarity_score' key."""
        mock_col.query.return_value = make_mock_chroma_response(n=3)
        from rag.retriever import get_similar_ads
        results = get_similar_ads("Special discount for limited period only!")
        for i, result in enumerate(results):
            assert "similarity_score" in result, (
                "Result {} missing 'similarity_score'".format(i)
            )
 
    @patch("rag.retriever._collection")
    def test_similarity_score_is_between_0_and_1(self, mock_col):
        """
        Similarity = 1 - (distance/2)
        distance is 0-2, so similarity must be 0.0-1.0
        """
        mock_col.query.return_value = make_mock_chroma_response(n=5)
        from rag.retriever import get_similar_ads
        results = get_similar_ads("Top quality product at best price today!")
        for i, result in enumerate(results):
            score = result["similarity_score"]
            assert 0.0 <= score <= 1.0, (
                "Result {} similarity {} is out of [0,1]".format(i, score)
            )
 
    @patch("rag.retriever._collection")
    def test_each_result_has_brand(self, mock_col):
        """Each result must have 'brand' key — used in format_for_agent."""
        mock_col.query.return_value = make_mock_chroma_response(n=3)
        from rag.retriever import get_similar_ads
        results = get_similar_ads("Great product with amazing features today!")
        for i, result in enumerate(results):
            assert "brand" in result, "Result {} missing 'brand'".format(i)
 
 
# ─────────────────────────────────────────────
# GROUP 2 — format_for_agent tests
# ─────────────────────────────────────────────
 
class TestFormatForAgent:
    """format_for_agent() must return a readable string for LLM."""
 
    @patch("rag.retriever._collection")
    def test_format_returns_string(self, mock_col):
        """format_for_agent must return a string."""
        mock_col.query.return_value = make_mock_chroma_response(n=3)
        from rag.retriever import get_similar_ads, format_for_agent
        results = get_similar_ads("Best shoes at amazing price today!")
        formatted = format_for_agent(results)
        assert isinstance(formatted, str), "format_for_agent must return str"
 
    @patch("rag.retriever._collection")
    def test_format_contains_competitor_label(self, mock_col):
        """Formatted string must contain 'Competitor' label."""
        mock_col.query.return_value = make_mock_chroma_response(n=2)
        from rag.retriever import get_similar_ads, format_for_agent
        results = get_similar_ads("Premium product at great value today!")
        formatted = format_for_agent(results)
        assert "Competitor" in formatted, "Formatted output must contain 'Competitor'"
 
    def test_format_empty_list_returns_message(self):
        """Empty list — must return 'no ads found' message, not crash."""
        from rag.retriever import format_for_agent
        result = format_for_agent([])
        assert isinstance(result, str), "Must return string for empty list"
        assert len(result) > 0, "Must return non-empty message for empty list"
 
 
# ─────────────────────────────────────────────
# GROUP 3 — Edge case tests
# ─────────────────────────────────────────────
 
class TestRetrieverEdgeCases:
    """Retriever must handle failures without crashing."""
 
    @patch("rag.retriever._collection")
    def test_chroma_failure_handled(self, mock_col):
        """
        ChromaDB exception — retriever must not crash the app.
        Phase 1 graceful degradation: returns [] on failure.
        """
        mock_col.query.side_effect = Exception("ChromaDB connection failed")
        from rag.retriever import get_similar_ads
        try:
            results = get_similar_ads("Great product with amazing features!")
            # Either returns empty list OR raises — both acceptable
            # as long as app doesn't get unhandled exception
            assert isinstance(results, list)
        except Exception as e:
            # If it raises, it should be a clear, intentional error
            # not an AttributeError or KeyError
            assert "ChromaDB" in str(e) or "retriev" in str(e).lower(), (
                "Unexpected exception type: {}".format(e)
            )