"""
tests/kg/test_kg_search_fallback.py — strict→loose fallback 테스트

kg.kg_search._run을 mock해서 Neo4j 없이 fallback 로직만 검증.
"""

from unittest.mock import patch, call
import pytest

import kg.kg_search as kg_mod
from kg.kg_search import search, LOOSE_MIN_RESULTS

# ── 최소 행 픽스처 ────────────────────────────────────────────────

def _make_row(place_id="p1", name="식당1"):
    return {
        "place_id": place_id,
        "name": name,
        "visitor_reviews": 100,
        "blog_reviews": 10,
        "address": "서울",
        "dist": 100,
        "matched_menu": None,
        "matched_menu_price": None,
        "matched_keywords": [],
        "avg_weight": None,
        "signature_menus": [],
    }


def _rows(n):
    """n개의 고유 place_id를 가진 행 리스트 반환."""
    return [_make_row(place_id=f"p{i}", name=f"식당{i}") for i in range(n)]


# ── 테스트 ────────────────────────────────────────────────────────

class TestStrictLooseFallback:

    def test_strict_enough_results(self):
        """_run이 5개 반환 → strict 충분, _run 1회만 호출."""
        driver = object()
        slots = {"category": "고기집", "keywords": ["가격/가성비"]}

        with patch("kg.kg_search._run", return_value=_rows(5)) as mock_run:
            result = search(driver, slots, k=10)

        assert result["search_mode"] == "strict"
        assert len(result["candidates"]) == 5
        assert mock_run.call_count == 1

    def test_strict_below_threshold_no_relaxable(self):
        """_run이 1개 반환 + keywords/facilities 없음 → fallback 없이 strict 반환, _run 1회."""
        driver = object()
        slots = {"category": "고기집"}  # no keywords, no facilities

        with patch("kg.kg_search._run", return_value=_rows(1)) as mock_run:
            result = search(driver, slots, k=10)

        assert result["search_mode"] == "strict"
        assert len(result["candidates"]) == 1
        assert mock_run.call_count == 1

    def test_loose_fallback_triggered(self):
        """strict 1개 → loose 5개, keywords 있음 → loose fallback 작동, _run 2회."""
        driver = object()
        slots = {"category": "고기집", "keywords": ["가격/가성비"]}

        call_count = 0
        def side_effect(drv, query, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _rows(1)   # strict: 부족
            return _rows(5)       # loose: 충분

        with patch("kg.kg_search._run", side_effect=side_effect) as mock_run:
            result = search(driver, slots, k=10)

        assert result["search_mode"] == "loose"
        assert len(result["candidates"]) == 5
        assert mock_run.call_count == 2

    def test_loose_fallback_drops_only_keyword_facility(self):
        """loose pass 때 _run 두 번째 호출 params에 keywords·facilities 없어야 함."""
        driver = object()
        slots = {
            "category": "고기집",
            "keywords": ["가격/가성비"],
            "facilities": ["주차"],
        }

        call_count = 0
        def side_effect(drv, query, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _rows(0)   # strict: 없음
            return _rows(4)       # loose: 있음

        with patch("kg.kg_search._run", side_effect=side_effect) as mock_run:
            result = search(driver, slots, k=10)

        assert mock_run.call_count == 2
        # 두 번째 call의 params에서 keywords·facilities 키 없어야 함
        second_call_params = mock_run.call_args_list[1][0][2]  # positional arg index 2
        assert "keywords" not in second_call_params
        assert "facilities" not in second_call_params
        # category는 유지
        assert "category" in second_call_params

    def test_search_mode_in_return(self):
        """search_mode 키가 strict/loose 양쪽 반환 dict에 모두 존재."""
        driver = object()

        # strict case
        with patch("kg.kg_search._run", return_value=_rows(5)):
            result_strict = search(driver, {"category": "고기집"}, k=10)
        assert "search_mode" in result_strict

        # loose case
        call_count = 0
        def side_effect(drv, query, params):
            nonlocal call_count
            call_count += 1
            return _rows(1) if call_count == 1 else _rows(5)

        with patch("kg.kg_search._run", side_effect=side_effect):
            result_loose = search(driver, {"category": "고기집", "keywords": ["맛"]}, k=10)
        assert "search_mode" in result_loose
        assert result_loose["search_mode"] == "loose"
