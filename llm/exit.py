"""LLM exit module — KG 검색 결과를 한국어 자연어 추천으로 변환."""

from __future__ import annotations

_SYSTEM_PROMPT = """\
당신은 관악구 맛집 추천 어시스턴트입니다.
아래 후보 식당 목록을 바탕으로 사용자에게 자연스러운 한국어로 추천해 주세요.

규칙:
1. KG에 명시된 정보만 사용하세요. 후보에 없는 메뉴·시설은 절대 지어내지 마세요.
2. ratio나 weight 수치를 "참여자 X%가~" 형태로 표현하지 마세요. 대신 "언급이 특히 많아요", "리뷰에서 자주 등장해요" 등으로 표현하세요.
3. 표본이 적은 식당(review_participant_count < 20)의 키워드·메뉴 언급은 주의해서 다루세요.
4. 검색 모드가 "loose"이면 키워드/시설 조건을 일부 완화한 결과임을 자연스럽게 언급하세요.
5. 추천은 2-4개 식당으로 압축하고, 각각 한두 문장으로 간결하게 소개하세요.\
"""


def _build_user_message(
    candidates: list[dict],
    slots: dict,
    radius_used: int | None,
    search_mode: str,
) -> str:
    """후보 식당 목록을 LLM 입력용 구조화 문자열로 변환."""
    radius_str = f"{radius_used}m 이내" if radius_used is not None else "미지정"
    lines = [
        "[검색 조건]",
        f"카테고리: {slots.get('category', '미지정')}",
        f"역: {slots.get('station', '미지정')}",
        f"반경: {radius_str}",
        f"검색모드: {search_mode}",
        "",
        "[후보 식당 목록]",
    ]

    for idx, c in enumerate(candidates, start=1):
        dist_val = c.get("dist")
        dist_str = str(round(dist_val)) + "m" if dist_val is not None else "거리 미상"

        lines.append(f"{idx}. {c.get('name', '이름 미상')} ({dist_str})")
        lines.append(f"   주소: {c.get('address', '-')}")
        lines.append(
            f"   방문자 리뷰: {c.get('visitor_reviews', 0)}건"
            f" (참여자: {c.get('review_participant_count', 0)}명)"
        )

        matched_menu = c.get("matched_menu")
        if matched_menu:
            price = c.get("matched_menu_price")
            price_str = f" ({price}원)" if price else ""
            lines.append(f"   검색 메뉴: {matched_menu}{price_str}")

        matched_kw = c.get("matched_keywords")
        if matched_kw:
            kw_names = ", ".join(k["name"] for k in matched_kw)
            lines.append(f"   매칭 키워드: {kw_names}")

        sig_menus = c.get("signature_menus")
        if sig_menus:
            top3 = [m["name"] for m in sig_menus[:3]]
            lines.append(f"   대표 메뉴: {', '.join(top3)}")

        lines.append("")

    return "\n".join(lines)


def recommend(
    candidates: list[dict],
    slots: dict,
    radius_used: int | None,
    search_mode: str,
    llm_client,
) -> str:
    """KG 검색 결과를 바탕으로 한국어 자연어 추천 문자열 반환.

    Args:
        candidates: KG 검색 결과 식당 목록.
        slots: CoE가 추출한 슬롯 dict.
        radius_used: 실제 검색에 사용된 반경(m). None이면 미지정.
        search_mode: "strict" 또는 "loose".
        llm_client: anthropic.Anthropic 인스턴스. None이면 폴백 반환.

    Returns:
        한국어 추천 문자열. 예외 발생 없이 항상 str을 반환.
    """
    if not candidates:
        return "죄송해요, 조건에 맞는 식당을 찾지 못했어요."

    if llm_client is None:
        return "후보 식당: " + ", ".join(c.get("name", "이름 미상") for c in candidates)

    user_message = _build_user_message(candidates, slots, radius_used, search_mode)

    try:
        response = llm_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception:
        return "죄송해요, 추천 생성 중 오류가 발생했어요."
