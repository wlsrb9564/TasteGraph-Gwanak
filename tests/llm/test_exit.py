from unittest.mock import MagicMock

from llm.exit import recommend

# ── minimal candidate fixture ─────────────────────────────────────

CANDIDATE = {
    "place_id": "p1",
    "name": "신림식당",
    "address": "서울 관악구",
    "dist": 300,
    "visitor_reviews": 150,
    "blog_reviews": 20,
    "review_participant_count": 150,
    "matched_menu": "냉면",
    "matched_menu_price": 9000,
    "matched_keywords": [{"name": "가격/가성비", "weight": 0.3}],
    "avg_weight": 0.3,
    "signature_menus": [{"name": "냉면", "ratio": 1.2}],
}

SLOTS = {"category": "한식", "station": "신림역"}


def _make_mock_client(response_text="추천 결과입니다."):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=response_text)]
    mock_client.messages.create.return_value = mock_response
    return mock_client


# ── test 1: empty candidates → no LLM call, returns 죄송 string ──

def test_empty_candidates_no_llm_call():
    mock_client = _make_mock_client()
    result = recommend([], SLOTS, radius_used=500, search_mode="strict", llm_client=mock_client)
    assert result == "죄송해요, 조건에 맞는 식당을 찾지 못했어요."
    mock_client.messages.create.assert_not_called()


# ── test 2: llm_client=None → fallback listing, no error ─────────

def test_none_client_returns_fallback():
    result = recommend([CANDIDATE], SLOTS, radius_used=500, search_mode="strict", llm_client=None)
    assert result.startswith("후보 식당: ")
    assert "신림식당" in result


# ── test 3: normal case → client.messages.create called once ──────

def test_llm_called_with_candidates():
    mock_client = _make_mock_client()
    result = recommend([CANDIDATE], SLOTS, radius_used=500, search_mode="strict", llm_client=mock_client)
    mock_client.messages.create.assert_called_once()
    assert isinstance(result, str)
    assert len(result) > 0


# ── test 4: loose mode → user message contains "loose" or "완화" ──

def test_loose_mode_context_in_prompt():
    mock_client = _make_mock_client()
    recommend([CANDIDATE], SLOTS, radius_used=800, search_mode="loose", llm_client=mock_client)
    call_kwargs = mock_client.messages.create.call_args
    # extract user message content from the messages argument
    messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0] if call_kwargs.args else None
    if messages is None:
        # messages passed as keyword arg
        messages = call_kwargs[1].get("messages") or call_kwargs[0].get("messages", [])
    user_content = ""
    for msg in messages:
        if msg.get("role") == "user":
            user_content += msg.get("content", "")
    assert "loose" in user_content or "완화" in user_content, (
        f"Expected 'loose' or '완화' in user message, got: {user_content!r}"
    )


# ── test 5: LLM response text returned as-is ─────────────────────

def test_llm_response_text_returned():
    expected_text = "오늘은 신림식당을 추천해요!"
    mock_client = _make_mock_client(response_text=expected_text)
    result = recommend([CANDIDATE], SLOTS, radius_used=500, search_mode="strict", llm_client=mock_client)
    assert result == expected_text
