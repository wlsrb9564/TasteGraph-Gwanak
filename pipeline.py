from coe import extract
from kg.kg_search import search
from llm import recommend


def run(query: str, driver, llm_client=None) -> str:
    """자연어 쿼리 → 한국어 추천 문자열.

    LLM 호출 최대 2회:
      1. CoE Layer 2 (anchor 없을 때만, extract() 내부)
      2. LLM 출구 recommend() (항상)

    Args:
        query: 사용자 입력 문자열
        driver: neo4j.GraphDatabase.driver 인스턴스
        llm_client: anthropic.Anthropic 인스턴스 (None이면 LLM 스텝 스킵)

    Returns:
        추천 문자열, 또는 되묻기 질문 문자열
    """
    slots = extract(query, llm_client=llm_client)

    if slots.get("clarification_needed"):
        return slots["clarification_needed"]

    result = search(driver, slots)
    return recommend(
        candidates=result["candidates"],
        slots=slots,
        radius_used=result["radius_used"],
        search_mode=result["search_mode"],
        llm_client=llm_client,
    )
