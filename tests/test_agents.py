"""
tests/test_agents.py
Tests for agents/analyst.py and agents/builder.py
 
Actual function names:
  analyst.py  -> analyze_gaps(user_ad, product_description)
  builder.py  -> rewrite_ad(original_ad, gaps)
               -> run_full_pipeline(user_ad, product_description)
 
Gaps format (analyst returns list of dicts):
  [{"gap": "...", "severity": "high", "competitor_does": "..."}]
 
Builder return keys: rewritten_ad, changes_made, word_count
Pipeline return keys: success, gaps, rewritten_ad, changes_made, word_count
"""
 
import pytest
from unittest.mock import patch, MagicMock
 
 
# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
 
def make_analyst_mock_response():
    """
    analyst.py LLM se list of dicts expect karta hai.
    Har dict mein: gap, severity, competitor_does
    """
    mock = MagicMock()
    mock.choices[0].message.content = (
        '[{"gap": "No urgency trigger", "severity": "high", '
        '"competitor_does": "Use limited time offers"}, '
        '{"gap": "Missing social proof", "severity": "medium", '
        '"competitor_does": "Add customer count or ratings"}, '
        '{"gap": "Weak call to action", "severity": "high", '
        '"competitor_does": "End with Shop Now or Order Today"}]'
    )
    return mock
 
 
def make_builder_mock_response():
    """
    builder.py LLM se rewritten ad + CHANGES section expect karta hai.
    Format: [ad text] --- CHANGES: - change1 - change2
    """
    mock = MagicMock()
    mock.choices[0].message.content = (
        "Hurry! Only 24 hours left. Grab the best deal now. "
        "Join 10,000 happy customers today!\n"
        "---\n"
        "CHANGES:\n"
        "- Added 24-hour urgency\n"
        "- Added social proof (10,000 customers)\n"
        "- Stronger CTA (Grab now)"
    )
    return mock
 
 
def make_gaps_list():
    """
    Actual gaps format — list of dicts.
    builder.py mein gap.get("severity") call hota hai.
    Isliye strings nahi, dicts pass karne padte hain.
    """
    return [
        {
            "gap": "No urgency trigger",
            "severity": "high",
            "competitor_does": "Use limited time offers like 24 hours only"
        },
        {
            "gap": "Missing social proof",
            "severity": "medium",
            "competitor_does": "Add customer count or star ratings"
        }
    ]
 
 
# ─────────────────────────────────────────────
# GROUP 1 — Analyst agent tests
# ─────────────────────────────────────────────
 
class TestAnalystAgent:
    """Analyst must identify gaps and return list of dicts."""
 
    @patch("agents.analyst.client.chat.completions.create")
    def test_analyst_returns_gaps_list(self, mock_groq):
        """analyze_gaps() must return a non-empty list."""
        mock_groq.return_value = make_analyst_mock_response()
        from agents.analyst import analyze_gaps
        result = analyze_gaps(
            user_ad="Buy our product. It is good.",
            product_description="Premium quality shoes for everyday use."
        )
        assert isinstance(result, list), "analyze_gaps must return a list"
        assert len(result) > 0, "Gaps list must not be empty"
 
    @patch("agents.analyst.client.chat.completions.create")
    def test_analyst_gaps_are_dicts_with_required_keys(self, mock_groq):
        """Each gap must be a dict with gap, severity, competitor_does keys."""
        mock_groq.return_value = make_analyst_mock_response()
        from agents.analyst import analyze_gaps
        result = analyze_gaps(
            user_ad="Good product at fair price available now for all.",
            product_description="Affordable daily-use footwear brand."
        )
        for i, gap in enumerate(result):
            assert isinstance(gap, dict), "Gap {} must be a dict".format(i)
            assert "gap" in gap, "Gap {} missing 'gap' key".format(i)
            assert "severity" in gap, "Gap {} missing 'severity' key".format(i)
            assert "competitor_does" in gap, "Gap {} missing 'competitor_does' key".format(i)
 
    @patch("agents.analyst.client.chat.completions.create")
    def test_analyst_severity_is_valid(self, mock_groq):
        """Severity must be one of: high, medium, low."""
        mock_groq.return_value = make_analyst_mock_response()
        from agents.analyst import analyze_gaps
        result = analyze_gaps(
            user_ad="Great shoes at amazing price buy now today for you.",
            product_description="Sports footwear for active lifestyle."
        )
        valid_severities = {"high", "medium", "low"}
        for gap in result:
            assert gap["severity"] in valid_severities, (
                "Invalid severity: {}".format(gap["severity"])
            )
 
    @patch("agents.analyst.client.chat.completions.create")
    def test_analyst_handles_llm_failure_with_fallback(self, mock_groq):
        """LLM exception — must return fallback gaps list, not crash."""
        mock_groq.side_effect = Exception("Rate limit exceeded")
        from agents.analyst import analyze_gaps
        result = analyze_gaps(
            user_ad="Buy product now at good price for everyone today.",
            product_description="General consumer product."
        )
        # Fallback returns _get_fallback_gaps() — still a list
        assert isinstance(result, list), "Fallback must return a list"
        assert len(result) > 0, "Fallback list must not be empty"
 
 
# ─────────────────────────────────────────────
# GROUP 2 — Builder agent tests
# ─────────────────────────────────────────────
 
class TestBuilderAgent:
    """Builder must rewrite ad and return correct keys."""
 
    @patch("agents.builder.client.chat.completions.create")
    def test_builder_returns_rewritten_ad(self, mock_groq):
        """Builder output must have 'rewritten_ad' key."""
        mock_groq.return_value = make_builder_mock_response()
        from agents.builder import rewrite_ad
        result = rewrite_ad(
            original_ad="Buy our product. It is good.",
            gaps=make_gaps_list()
        )
        assert "rewritten_ad" in result, "Builder must have 'rewritten_ad' key"
        assert isinstance(result["rewritten_ad"], str), "rewritten_ad must be string"
        assert len(result["rewritten_ad"]) > 0, "rewritten_ad must not be empty"
 
    @patch("agents.builder.client.chat.completions.create")
    def test_builder_returns_changes_made(self, mock_groq):
        """Builder output must have 'changes_made' key."""
        mock_groq.return_value = make_builder_mock_response()
        from agents.builder import rewrite_ad
        result = rewrite_ad(
            original_ad="Good product available now at best price today.",
            gaps=make_gaps_list()
        )
        assert "changes_made" in result, "Builder must have 'changes_made' key"
 
    @patch("agents.builder.client.chat.completions.create")
    def test_builder_returns_word_count(self, mock_groq):
        """Builder output must have 'word_count' key."""
        mock_groq.return_value = make_builder_mock_response()
        from agents.builder import rewrite_ad
        result = rewrite_ad(
            original_ad="Amazing product at great price available for everyone.",
            gaps=make_gaps_list()
        )
        assert "word_count" in result, "Builder must have 'word_count' key"
        assert isinstance(result["word_count"], int), "word_count must be int"
 
    @patch("agents.builder.client.chat.completions.create")
    def test_builder_empty_gaps_returns_original(self, mock_groq):
        """
        Empty gaps list — builder returns original ad unchanged.
        No LLM call needed — this is handled before the API call.
        """
        from agents.builder import rewrite_ad
        original = "Buy our product today at the best price available now."
        result = rewrite_ad(original_ad=original, gaps=[])
 
        assert result["rewritten_ad"] == original, (
            "Empty gaps should return original ad unchanged"
        )
        # mock_groq should NOT have been called
        mock_groq.assert_not_called()
 
    @patch("agents.builder.client.chat.completions.create")
    def test_builder_handles_llm_failure(self, mock_groq):
        """LLM exception — builder returns original ad, not crash."""
        mock_groq.side_effect = Exception("Connection timeout")
        from agents.builder import rewrite_ad
        original = "Buy product today at amazing price guaranteed now."
        result = rewrite_ad(original_ad=original, gaps=make_gaps_list())
 
        # Fallback: original ad returned
        assert isinstance(result, dict), "Must return dict on LLM failure"
        assert "rewritten_ad" in result, "Fallback must have rewritten_ad key"
        assert result["rewritten_ad"] == original, (
            "On failure, original ad should be returned"
        )
 
 
# ─────────────────────────────────────────────
# GROUP 3 — Full pipeline tests
# ─────────────────────────────────────────────
 
class TestFullPipeline:
    """
    run_full_pipeline(user_ad, product_description) — app.py isko call karta hai.
    Return keys: success, gaps, rewritten_ad, changes_made, word_count
    """
 
    @patch("agents.builder.client.chat.completions.create")
    @patch("agents.analyst.client.chat.completions.create")
    @patch("rag.retriever._collection")
    def test_pipeline_returns_all_required_keys(
        self, mock_collection, mock_analyst, mock_builder
    ):
        """Pipeline output must have all keys app.py uses."""
        mock_collection.query.return_value = {
            "documents": [["Great ad with amazing discount and offer now!"]],
            "metadatas": [[{"category": "FMCG", "brand": "TestBrand",
                           "platform": "Instagram", "hook": "Great",
                           "sentiment": "positive", "has_cta": "True",
                           "price_mentioned": "False", "keywords": "discount"}]],
            "distances": [[0.15]]
        }
        mock_analyst.return_value = make_analyst_mock_response()
        mock_builder.return_value = make_builder_mock_response()
 
        from agents.builder import run_full_pipeline
        result = run_full_pipeline(
            user_ad="Buy our product. Good price. Available now today.",
            product_description="Premium quality shoes for everyday use."
        )
 
        required_keys = ["success", "gaps", "rewritten_ad", "changes_made", "word_count"]
        for key in required_keys:
            assert key in result, (
                "Pipeline missing key: '{}'. Got: {}".format(key, list(result.keys()))
            )
 
    @patch("agents.builder.client.chat.completions.create")
    @patch("agents.analyst.client.chat.completions.create")
    @patch("rag.retriever._collection")
    def test_pipeline_success_flag_true_on_success(
        self, mock_collection, mock_analyst, mock_builder
    ):
        """Successful pipeline must have success:True."""
        mock_collection.query.return_value = {
            "documents": [["Best product with great value and offer!"]],
            "metadatas": [[{"category": "Tech", "brand": "Brand",
                           "platform": "FB", "hook": "Best",
                           "sentiment": "positive", "has_cta": "True",
                           "price_mentioned": "True", "keywords": "product"}]],
            "distances": [[0.20]]
        }
        mock_analyst.return_value = make_analyst_mock_response()
        mock_builder.return_value = make_builder_mock_response()
 
        from agents.builder import run_full_pipeline
        result = run_full_pipeline(
            user_ad="Amazing shoes at unbeatable price. Buy now today!",
            product_description="Premium leather shoes, handcrafted quality."
        )
        assert result["success"] is True, (
            "Successful pipeline must have success:True"
        )
 
    @patch("agents.builder.client.chat.completions.create")
    @patch("agents.analyst.client.chat.completions.create")
    @patch("rag.retriever._collection")
    def test_pipeline_gaps_is_list(
        self, mock_collection, mock_analyst, mock_builder
    ):
        """Pipeline gaps must be a list."""
        mock_collection.query.return_value = {
            "documents": [["Top quality deal available now for you!"]],
            "metadatas": [[{"category": "FMCG", "brand": "X",
                           "platform": "FB", "hook": "Top",
                           "sentiment": "positive", "has_cta": "True",
                           "price_mentioned": "False", "keywords": "quality"}]],
            "distances": [[0.18]]
        }
        mock_analyst.return_value = make_analyst_mock_response()
        mock_builder.return_value = make_builder_mock_response()
 
        from agents.builder import run_full_pipeline
        result = run_full_pipeline(
            user_ad="Good product at fair price available now for all.",
            product_description="Daily use consumer product."
        )
        assert isinstance(result["gaps"], list), "gaps must be a list"
 