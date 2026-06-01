"""
kg_search.py — 단계 A: KG 검색 함수

슬롯 dict → 후보 식당 리스트. LLM 없이 순수 Cypher.

빌더 함수들이 Cypher 블록을 dict로 반환하고,
search() 어셈블러가 이를 조합해 최종 쿼리를 실행한다.

사용 예:
    from kg.kg_search import search
    res = search(driver, {"category": "고기집", "station": "서울대입구역"})
    res = search(driver, {"menu": "냉면", "station": "신림역"})
    res = search(driver, {"keywords": ["가격/가성비"], "station": "낙성대역"})
    res = search(driver, {"facilities": ["주차", "예약"], "station": "서울대입구역"})
    res = search(driver, {"menu": "삼겹살", "keywords": ["가격/가성비"], "facilities": ["주차"]})
"""

import json
from pathlib import Path

_DICTS_DIR = Path(__file__).parent.parent / "dicts"
_raw = json.loads((_DICTS_DIR / "station_coords.json").read_text(encoding="utf-8"))
STATIONS = {name: (v["lat"], v["lng"]) for name, v in _raw.items()}

RADIUS_STEPS = [500, 800, 1200, 1800]
MIN_PARTICIPANTS = 20  # ratio/weight 기반 순위에서 표본 임계값
LOOSE_MIN_RESULTS = 3  # strict 결과가 이 수 미만이면 loose fallback 시도


# ── 빌더 함수들 ───────────────────────────────────────────────────
# 각 빌더는 {"match": [], "where": [], "params": {}, "_meta": {}} 반환
# 슬롯 조건 없으면 None → 어셈블러가 건너뜀

def _build_category_block(slots):
    if not slots.get("category"):
        return None
    return {
        "match": ["MATCH (r)-[:IN_CATEGORY]->(:Category {name: $category})"],
        "where": [],
        "params": {"category": slots["category"]},
        "_meta": {},
    }


def _build_district_block(slots):
    if not slots.get("district"):
        return None
    return {
        "match": ["MATCH (r)-[:LOCATED_IN]->(:District {name: $district})"],
        "where": [],
        "params": {"district": slots["district"]},
        "_meta": {},
    }


def _build_location_block(slots):
    """역 이름 또는 직접 좌표 → 거리 필터 블록."""
    loc = _resolve_location(slots)
    if not loc:
        return None
    lat, lng = loc
    return {
        "match": [],
        "where": [
            "r.location IS NOT NULL",
            "point.distance(r.location, point({latitude: $lat, longitude: $lng})) <= $radius",
        ],
        "params": {"lat": lat, "lng": lng},
        "_meta": {
            "has_location": True,
            "start_radius": slots.get("radius", RADIUS_STEPS[0]),
        },
    }


def _build_menu_block(slots):
    """Menu CONTAINS 검색 블록 (패턴 ②).
    표본 임계값 미만 식당 제외.
    """
    if not slots.get("menu"):
        return None
    return {
        "match": ["MATCH (r)-[hm:HAS_MENU]->(m:Menu)"],
        "where": [
            "m.name CONTAINS $menu",
            f"r.review_participant_count >= {MIN_PARTICIPANTS}",
        ],
        "params": {"menu": slots["menu"]},
        "_meta": {"has_menu": True},
    }


def _build_keyword_block(slots):
    """ReviewKeyword 가중 검색 블록 (패턴 ③).

    복수 키워드 AND: 지정한 키워드를 모두 보유한 식당만 반환.
    정렬 기준: avg(weight) DESC — 식당 간 비교에 적합한 정규화값.
    표본 임계값 미만 식당 제외.

    슬롯:
        keywords: list[str]  예) ["가격/가성비", "분위기/인테리어"]
                  str 하나도 허용 → 리스트로 자동 변환
    """
    raw = slots.get("keywords")
    if not raw:
        return None
    keywords = [raw] if isinstance(raw, str) else list(raw)
    if not keywords:
        return None
    return {
        "match": ["MATCH (r)-[rk:HAS_REVIEW_KEYWORD]->(kw:ReviewKeyword)"],
        "where": [
            "kw.name IN $keywords",
            f"r.review_participant_count >= {MIN_PARTICIPANTS}",
        ],
        "params": {"keywords": keywords},
        "_meta": {"has_keyword": True},
    }


def _build_facility_block(slots):
    """시설 필터 블록 (패턴 ④).

    복수 시설 AND: 지정한 시설을 모두 보유한 식당만 반환.

    슬롯:
        facilities: list[str]  예) ["주차", "예약"]
                    str 하나도 허용 → 리스트로 자동 변환
    """
    raw = slots.get("facilities")
    if not raw:
        return None
    facilities = [raw] if isinstance(raw, str) else list(raw)
    if not facilities:
        return None
    return {
        "match": ["MATCH (r)-[fo:OFFERS]->(fac:Facility)"],
        "where": ["fac.name IN $facilities"],
        "params": {"facilities": facilities},
        "_meta": {"has_facility": True},
    }


# ── 헬퍼 ─────────────────────────────────────────────────────────

def _resolve_location(slots):
    """슬롯에서 (lat, lng) 결정. 우선순위: 직접 좌표 > 역 이름."""
    if slots.get("lat") is not None and slots.get("lng") is not None:
        return (slots["lat"], slots["lng"])
    st = slots.get("station")
    if st:
        st = st.strip()
        if st not in STATIONS and (st + "역") in STATIONS:
            st = st + "역"
        if st in STATIONS:
            return STATIONS[st]
        raise ValueError(f"모르는 역 이름: {slots.get('station')}")
    return None


def _radius_ladder(start):
    """요청 반경에서 시작해 점진 확장하는 사다리."""
    ladder = [start] + [s for s in RADIUS_STEPS if s > start]
    seen, out = set(), []
    for r in ladder:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _run(driver, query, params):
    with driver.session() as session:
        return [dict(rec) for rec in session.run(query, **params)]


def _sort_signature_menus(rows):
    """signature_menus를 ratio DESC로 정렬 (Python 후처리)."""
    for row in rows:
        sigs = row.get("signature_menus") or []
        row["signature_menus"] = sorted(
            [s for s in sigs if s],
            key=lambda x: x.get("ratio", 0),
            reverse=True,
        )
    return rows


# ── 어셈블러 ─────────────────────────────────────────────────────

_SIG_MENUS_EXPR = (
    f"[(r)-[_ma:MENTIONED_AS]->(_mk:MenuKeyword) "
    f"WHERE r.review_participant_count >= {MIN_PARTICIPANTS} "
    f"| {{name: _mk.name, ratio: _ma.ratio}}][0..5] AS signature_menus"
)

_BASE_RETURN = """r.place_id             AS place_id,
           r.name                 AS name,
           r.visitor_review_count AS visitor_reviews,
           r.blog_review_count    AS blog_reviews,
           r.address              AS address"""


def _build_with_clause(has_menu, has_keyword, has_facility, dist_expr):
    """WITH 절 동적 조립.

    has_menu / has_keyword / has_facility 플래그 보고
    필요한 집계 항목만 리스트에 추가 → 문자열로 합침.
    HAVING 조건(matched_*_count = size(...))도 동적으로 추가.
    """
    if not (has_menu or has_keyword or has_facility):
        return ""

    with_parts = ["r"]
    having_parts = []

    if has_menu:
        with_parts.append(
            "collect({name: m.name, price: hm.price})[0] AS best_match"
        )
    if has_keyword:
        with_parts += [
            "count(DISTINCT kw)                                      AS matched_kw_count",
            "avg(rk.weight)                                          AS avg_weight",
            "collect(DISTINCT {name: kw.name, weight: rk.weight})   AS matched_keywords",
        ]
        having_parts.append("matched_kw_count = size($keywords)")
    if has_facility:
        with_parts.append(
            "count(DISTINCT fac)                                     AS matched_fac_count"
        )
        having_parts.append("matched_fac_count = size($facilities)")

    with_parts.append(f"{dist_expr} AS dist")

    clause = "WITH " + ",\n         ".join(with_parts)
    if having_parts:
        clause += "\n    WHERE " + " AND ".join(having_parts)
    return clause


def _execute_search(driver, slots, k=10):
    """슬롯 dict로 Cypher 쿼리를 조립·실행해 후보 리스트를 반환한다.

    search()의 내부 실행 엔진. strict/loose 양쪽에서 공유.

    반환:
        {"radius_used": int | None, "candidates": [...]}
    """
    blocks = [b for b in [
        _build_category_block(slots),
        _build_district_block(slots),
        _build_location_block(slots),
        _build_menu_block(slots),
        _build_keyword_block(slots),
        _build_facility_block(slots),
    ] if b is not None]

    # 블록 병합
    match_parts = ["MATCH (r:Restaurant)"]
    where_parts = []
    params = {"k": k}
    has_location = False
    has_menu = False
    has_keyword = False
    has_facility = False
    start_radius = RADIUS_STEPS[0]

    for block in blocks:
        match_parts.extend(block["match"])
        where_parts.extend(block["where"])
        params.update(block["params"])
        meta = block["_meta"]
        if meta.get("has_location"):
            has_location = True
            start_radius = meta["start_radius"]
        if meta.get("has_menu"):
            has_menu = True
        if meta.get("has_keyword"):
            has_keyword = True
        if meta.get("has_facility"):
            has_facility = True

    match_clause = "\n    ".join(match_parts)
    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    dist_expr = (
        "point.distance(r.location, point({latitude: $lat, longitude: $lng}))"
        if has_location else "null"
    )

    # ORDER BY: 위치 있으면 거리순, 키워드만 있으면 weight순, 나머지 리뷰순
    if has_location:
        order_clause = "ORDER BY dist ASC"
    elif has_keyword:
        order_clause = "ORDER BY avg_weight DESC"
    else:
        order_clause = "ORDER BY r.visitor_review_count DESC"

    # WITH 절 동적 조립
    need_with = has_menu or has_keyword or has_facility
    agg_clause = _build_with_clause(has_menu, has_keyword, has_facility, dist_expr)

    # RETURN 필드 동적 조립
    dist_in_return = "dist" if need_with else f"{dist_expr} AS dist"

    extra_parts = []
    extra_parts += (
        ["best_match.name AS matched_menu", "best_match.price AS matched_menu_price"]
        if (has_menu and need_with)
        else ["null AS matched_menu", "null AS matched_menu_price"]
    )
    extra_parts += (
        ["matched_keywords", "avg_weight"]
        if has_keyword
        else ["[] AS matched_keywords", "null AS avg_weight"]
    )
    extra_return = ",\n           ".join(extra_parts)

    query = f"""
    {match_clause}
    {where_clause}
    {agg_clause}
    RETURN {_BASE_RETURN},
           {extra_return},
           {_SIG_MENUS_EXPR},
           {dist_in_return}
    {order_clause}
    LIMIT $k
    """

    if has_location:
        rows = []
        radius = start_radius
        for radius in _radius_ladder(start_radius):
            params["radius"] = radius
            rows = _run(driver, query, params)
            if len(rows) >= k:
                return {"radius_used": radius, "candidates": _sort_signature_menus(rows)}
        return {"radius_used": radius, "candidates": _sort_signature_menus(rows)}

    rows = _run(driver, query, params)
    return {"radius_used": None, "candidates": _sort_signature_menus(rows)}


def search(driver, slots, k=10):
    """슬롯 dict → 후보 식당 리스트 (strict→loose 2단계 폴백 포함).

    슬롯 (전부 optional, 있는 것만 Cypher 블록으로 조립):
        category   : Category.name           예) "고기집"
        station    : 역 이름                 예) "서울대입구역"
        lat, lng   : 직접 좌표 (역 대신)
        radius     : 시작 반경 m, 기본 500. 폴백 사다리: 500→800→1200→1800
        district   : District.name
        menu       : 메뉴 키워드             예) "냉면"       (패턴 ②)
        keywords   : 리뷰키워드 리스트        예) ["가격/가성비"] (패턴 ③)
        facilities : 시설 리스트             예) ["주차", "예약"] (패턴 ④)

    폴백 전략:
        1. strict 패스: 모든 슬롯 적용
        2. strict 결과 < LOOSE_MIN_RESULTS이고 keywords/facilities 있으면:
           loose 패스: keywords·facilities 제거 후 재실행
        category·station/위치·menu 는 항상 유지.

    반환:
        {
          "radius_used": int | None,
          "candidates": [
            { place_id, name, visitor_reviews, blog_reviews, address,
              dist,
              matched_menu, matched_menu_price,
              matched_keywords, avg_weight,
              signature_menus },
          ],
          "search_mode": "strict" | "loose",
        }
    """
    strict = _execute_search(driver, slots, k)
    if len(strict["candidates"]) >= LOOSE_MIN_RESULTS:
        return {**strict, "search_mode": "strict"}

    # fallback 시도 가능한 슬롯이 있을 때만
    has_relaxable = slots.get("keywords") or slots.get("facilities")
    if not has_relaxable:
        return {**strict, "search_mode": "strict"}

    loose_slots = {key: v for key, v in slots.items() if key not in ("keywords", "facilities")}
    loose = _execute_search(driver, loose_slots, k)
    return {**loose, "search_mode": "loose"}


# 하위 호환: 기존 함수명
search_area_category = search
