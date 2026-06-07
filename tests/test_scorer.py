import pytest
from unittest.mock import patch, MagicMock

AD_SWEET_SPOT = (
    "Buy now and save big today with our amazing limited time offer "
    "for premium quality products at unbeatable price guaranteed forever."
)
AD_SHORT = "Buy now. Best price. Act today."

def make_mock_llm_response(hook=7, sentiment=6, keywords=5, clarity=7):
    fake_json = (
        '{{"hook_strength": {}, '
        '"sentiment_stability": {}, '
        '"keyword_density": {}, '
        '"clarity": {}}}'
    ).format(hook, sentiment, keywords, clarity)
    mock_response = MagicMock()
    mock_response.choices[0].message.content = fake_json
    return mock_response

class TestScoreRange:

    @patch("scoring.scorer.get_cached", return_value=None)
    @patch("scoring.scorer.set_cache")
    @patch("scoring.scorer.client.chat.completions.create")
    def test_score_within_range_normal_ad(self, mock_groq, mock_set, mock_get):
        mock_groq.return_value = make_mock_llm_response(hook=7, sentiment=6, keywords=5, clarity=7)
        from scoring.scorer import calculate_viral_score
        result = calculate_viral_score(AD_SWEET_SPOT)
        assert "total_score" in result
        assert 0 <= result["total_score"] <= 100

    @patch("scoring.scorer.get_cached", return_value=None)
    @patch("scoring.scorer.set_cache")
    @patch("scoring.scorer.client.chat.completions.create")
    def test_score_with_maximum_llm_values_is_100(self, mock_groq, mock_set, mock_get):
        mock_groq.return_value = make_mock_llm_response(hook=10, sentiment=10, keywords=10, clarity=10)
        from scoring.scorer import calculate_viral_score
        result = calculate_viral_score(AD_SWEET_SPOT)
        assert result["total_score"] == 100, "Got {}".format(result["total_score"])

    @patch("scoring.scorer.get_cached", return_value=None)
    @patch("scoring.scorer.set_cache")
    @patch("scoring.scorer.client.chat.completions.create")
    def test_score_with_minimum_llm_values_is_low(self, mock_groq, mock_set, mock_get):
        mock_groq.return_value = make_mock_llm_response(hook=1, sentiment=1, keywords=1, clarity=1)
        from scoring.scorer import calculate_viral_score
        result = calculate_viral_score(AD_SWEET_SPOT)
        assert 0 <= result["total_score"] <= 30, "Got {}".format(result["total_score"])

class TestScoringFormula:

    @patch("scoring.scorer.get_cached", return_value=None)
    @patch("scoring.scorer.set_cache")
    @patch("scoring.scorer.client.chat.completions.create")
    def test_result_has_breakdown(self, mock_groq, mock_set, mock_get):
        mock_groq.return_value = make_mock_llm_response(hook=8, sentiment=6, keywords=7, clarity=9)
        from scoring.scorer import calculate_viral_score
        result = calculate_viral_score(AD_SWEET_SPOT)
        assert "breakdown" in result
        for field in ["hook_strength", "sentiment_stability", "keyword_density", "clarity", "length_score"]:
            assert field in result["breakdown"], "Missing: {}".format(field)

    @patch("scoring.scorer.get_cached", return_value=None)
    @patch("scoring.scorer.set_cache")
    @patch("scoring.scorer.client.chat.completions.create")
    def test_higher_llm_values_give_higher_score(self, mock_groq, mock_set, mock_get):
        from scoring.scorer import calculate_viral_score
        mock_groq.return_value = make_mock_llm_response(hook=2, sentiment=2, keywords=2, clarity=2)
        score_low = calculate_viral_score(AD_SWEET_SPOT)["total_score"]
        mock_groq.return_value = make_mock_llm_response(hook=9, sentiment=9, keywords=9, clarity=9)
        score_high = calculate_viral_score(AD_SWEET_SPOT)["total_score"]
        assert score_high > score_low, "High {} vs Low {}".format(score_high, score_low)

    @patch("scoring.scorer.get_cached", return_value=None)
    @patch("scoring.scorer.set_cache")
    @patch("scoring.scorer.client.chat.completions.create")
    def test_result_has_grade(self, mock_groq, mock_set, mock_get):
        mock_groq.return_value = make_mock_llm_response(hook=8, sentiment=7, keywords=6, clarity=8)
        from scoring.scorer import calculate_viral_score
        result = calculate_viral_score(AD_SWEET_SPOT)
        assert "grade" in result
        assert isinstance(result["grade"], str)

    @patch("scoring.scorer.get_cached", return_value=None)
    @patch("scoring.scorer.set_cache")
    @patch("scoring.scorer.client.chat.completions.create")
    def test_short_ad_scores_lower_than_sweet_spot(self, mock_groq, mock_set, mock_get):
        from scoring.scorer import calculate_viral_score
        mock_groq.return_value = make_mock_llm_response(hook=7, sentiment=7, keywords=7, clarity=7)
        score_sweet = calculate_viral_score(AD_SWEET_SPOT)["total_score"]
        mock_groq.return_value = make_mock_llm_response(hook=7, sentiment=7, keywords=7, clarity=7)
        score_short = calculate_viral_score(AD_SHORT)["total_score"]
        assert score_sweet > score_short, "Sweet {} vs Short {}".format(score_sweet, score_short)

class TestInputValidation:

    def test_empty_string_rejected(self):
        from scoring.scorer import calculate_viral_score
        result = calculate_viral_score("")
        assert result.get("error") is True

    def test_none_input_does_not_crash(self):
        from scoring.scorer import calculate_viral_score
        try:
            result = calculate_viral_score(None)
            assert isinstance(result, dict)
        except (TypeError, ValueError):
            pass

    def test_too_short_input_rejected(self):
        from scoring.scorer import calculate_viral_score
        result = calculate_viral_score("Buy")
        assert result.get("error") is True

    def test_whitespace_only_rejected(self):
        from scoring.scorer import calculate_viral_score
        result = calculate_viral_score("     ")
        assert result.get("error") is True

class TestLLMFailureHandling:

    @patch("scoring.scorer.get_cached", return_value=None)
    @patch("scoring.scorer.set_cache")
    @patch("scoring.scorer.client.chat.completions.create")
    def test_groq_exception_uses_fallback(self, mock_groq, mock_set, mock_get):
        mock_groq.side_effect = Exception("Rate limit exceeded")
        from scoring.scorer import calculate_viral_score
        result = calculate_viral_score(AD_SWEET_SPOT)
        assert isinstance(result, dict)
        assert "total_score" in result
        assert 0 <= result["total_score"] <= 100

    @patch("scoring.scorer.get_cached", return_value=None)
    @patch("scoring.scorer.set_cache")
    @patch("scoring.scorer.client.chat.completions.create")
    def test_invalid_json_uses_fallback(self, mock_groq, mock_set, mock_get):
        mock_bad = MagicMock()
        mock_bad.choices[0].message.content = "Sorry I cannot help."
        mock_groq.return_value = mock_bad
        from scoring.scorer import calculate_viral_score
        try:
            result = calculate_viral_score(AD_SWEET_SPOT)
            assert isinstance(result, dict)
            assert "total_score" in result
        except Exception as e:
            pytest.fail("Crashed: {}".format(e))
