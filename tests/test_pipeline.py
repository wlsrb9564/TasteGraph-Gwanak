from unittest.mock import MagicMock, patch

import pipeline


def _make_driver():
    return MagicMock()


def _anchor_slots():
    return {"station": "신림역", "category": "고기집"}


def _noanchor_slots():
    return {"station": None, "category": None, "menu": "삼겹살"}


def _search_result(candidates=None, radius_used=500, search_mode="strict"):
    return {
        "candidates": candidates if candidates is not None else [{"name": "식당1"}],
        "radius_used": radius_used,
        "search_mode": search_mode,
    }


# ── 1. clarification_needed 반환 시 search·recommend 호출 없음 ────────

def test_clarification_returned_without_search():
    driver = _make_driver()
    with (
        patch("pipeline.extract") as mock_extract,
        patch("pipeline.search") as mock_search,
        patch("pipeline.recommend") as mock_recommend,
    ):
        mock_extract.return_value = {"clarification_needed": "어느 지역인가요?"}

        result = pipeline.run("맛집 추천", driver)

        assert result == "어느 지역인가요?"
        mock_search.assert_not_called()
        mock_recommend.assert_not_called()


# ── 2. anchor 있는 경우 정상 흐름 (llm_client=None) ──────────────────

def test_anchor_path_no_llm_for_coe():
    driver = _make_driver()
    with (
        patch("pipeline.extract") as mock_extract,
        patch("pipeline.search") as mock_search,
        patch("pipeline.recommend") as mock_recommend,
    ):
        mock_extract.return_value = _anchor_slots()
        mock_search.return_value = _search_result()
        mock_recommend.return_value = "식당1 추천합니다."

        result = pipeline.run("신림역 고기집", driver, llm_client=None)

        assert result == "식당1 추천합니다."
        # extract는 llm_client=None 으로 호출돼야 함
        _, extract_kwargs = mock_extract.call_args
        assert extract_kwargs.get("llm_client") is None


# ── 3. anchor 없을 때 llm_client가 extract·recommend 양쪽에 전달됨 ───

def test_no_anchor_llm_used_for_coe():
    driver = _make_driver()
    mock_llm_client = MagicMock()
    with (
        patch("pipeline.extract") as mock_extract,
        patch("pipeline.search") as mock_search,
        patch("pipeline.recommend") as mock_recommend,
    ):
        mock_extract.return_value = _noanchor_slots()
        mock_search.return_value = _search_result()
        mock_recommend.return_value = "삼겹살 맛집 추천합니다."

        pipeline.run("삼겹살 맛집", driver, llm_client=mock_llm_client)

        _, extract_kwargs = mock_extract.call_args
        assert extract_kwargs.get("llm_client") is mock_llm_client

        _, recommend_kwargs = mock_recommend.call_args
        assert recommend_kwargs.get("llm_client") is mock_llm_client


# ── 4. 빈 candidates → recommend 반환값 그대로 통과 ─────────────────

def test_empty_candidates_passes_through():
    driver = _make_driver()
    sorry = "죄송해요, 조건에 맞는 식당을 찾지 못했어요."
    with (
        patch("pipeline.extract") as mock_extract,
        patch("pipeline.search") as mock_search,
        patch("pipeline.recommend") as mock_recommend,
    ):
        mock_extract.return_value = _anchor_slots()
        mock_search.return_value = _search_result(candidates=[], radius_used=None)
        mock_recommend.return_value = sorry

        result = pipeline.run("신림역 고기집", driver)

        assert result == sorry


# ── 5. run은 항상 str을 반환한다 ─────────────────────────────────────

def test_run_always_returns_string():
    driver = _make_driver()
    with (
        patch("pipeline.extract") as mock_extract,
        patch("pipeline.search") as mock_search,
        patch("pipeline.recommend") as mock_recommend,
    ):
        mock_extract.return_value = _anchor_slots()
        mock_search.return_value = _search_result()
        mock_recommend.return_value = "결과"

        result = pipeline.run("신림역 고기집", driver)

        assert isinstance(result, str)
