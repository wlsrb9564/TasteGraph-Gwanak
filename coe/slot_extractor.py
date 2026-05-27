"""
coe/slot_extractor.py — 단계 B: CoE 슬롯 추출

Layer 1: 정규식/사전 매칭 (항상 실행, LLM 없음)
Layer 2: Claude API 슬롯 추출 (anchor 없을 때만, 최대 1회)
"""

import json
import re
from pathlib import Path

# ── 사전 로드 ─────────────────────────────────────────────────────

_DICTS_DIR = Path(__file__).parent.parent / "dicts"

_station_data = json.loads((_DICTS_DIR / "station_coords.json").read_text(encoding="utf-8"))
_STATIONS = sorted(_station_data.keys(), key=len, reverse=True)  # 긴 이름 우선

_cat_data = json.loads((_DICTS_DIR / "category_mapping.json").read_text(encoding="utf-8"))
_CATEGORIES = sorted([k for k in _cat_data if k != "nan"], key=len, reverse=True)

_kw_data = json.loads((_DICTS_DIR / "keyword_categories.json").read_text(encoding="utf-8"))

# ── 카테고리 동의어 ────────────────────────────────────────────────

_CATEGORY_SYNONYMS: dict[str, str] = {
    "삼겹살집": "고기집", "삼겹살": "고기집", "고깃집": "고기집",
    "돼지고기": "고기집", "소고기": "고기집", "갈비집": "고기집",
    "치킨집": "닭요리", "치킨": "닭요리",
    "커피숍": "카페", "커피전문점": "카페",
    "빵집": "베이커리", "제과점": "베이커리",
    "라멘집": "면/만두", "라멘": "면/만두",
    "냉면집": "면/만두", "국수집": "면/만두", "칼국수집": "면/만두",
    "국밥집": "찌개/탕/국", "찌개집": "찌개/탕/국", "해장국집": "찌개/탕/국",
    "초밥집": "일식", "스시": "일식", "돈까스": "일식", "돈가스": "일식",
    "짜장면": "중식", "짬뽕": "중식",
    "피자집": "양식", "파스타집": "양식", "햄버거집": "양식",
    "포차": "술집", "호프집": "술집", "맥주집": "술집",
    "분식집": "분식",
}

# ── 시설 동의어 ───────────────────────────────────────────────────

_FACILITY_SYNONYMS: dict[str, str] = {
    "주차장": "주차", "주차": "주차",
    "예약가능": "예약", "예약": "예약",
    "테이크아웃": "포장", "포장주문": "포장", "포장": "포장",
    "배달가능": "배달", "배달": "배달",
}

# ── 키워드 역방향 매핑 ────────────────────────────────────────────

_STOP_WORDS_KW = {
    "이에요", "예요", "해요", "좋아요", "있어요", "많아요", "깨끗해요",
    "편해요", "멋져요", "맛있어요", "신선해요", "다양해요", "나와요",
    "빨리", "가까워요", "잘",
}


_TRAILING_PARTICLES = ("가", "이", "은", "는", "을", "를", "와", "과", "도", "로", "에", "의")
_VERB_ENDINGS = ("해요", "이에요", "예요", "아요", "어요")


def _stem(word: str) -> list[str]:
    """단어 끝 조사/어미를 제거한 어근 후보 반환 (원형 포함)."""
    stems = [word]
    for ending in _VERB_ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 2:
            stems.append(word[: -len(ending)])
            break
    for particle in _TRAILING_PARTICLES:
        if word.endswith(particle) and len(word) - 1 >= 2:
            stems.append(word[:-1])
            break
    return stems


def _build_keyword_reverse() -> dict[str, str]:
    reverse: dict[str, str] = {}
    for kw_name, phrases in _kw_data.items():
        for phrase in phrases:
            words = re.findall(r"[가-힣]{2,5}", phrase)
            for word in words:
                if word in _STOP_WORDS_KW:
                    continue
                for candidate in _stem(word):
                    if candidate not in _STOP_WORDS_KW and candidate not in reverse:
                        reverse[candidate] = kw_name
    return reverse


_KW_REVERSE: dict[str, str] = _build_keyword_reverse()

# ── 메뉴 불용어 ───────────────────────────────────────────────────

_STOP_WORDS_MENU = {
    "맛집", "추천", "근처", "어디", "좋은", "좋아", "좀", "알려줘", "알려",
    "줘", "어때", "있어", "있는", "없어", "없는", "먹고싶어", "먹고", "싶어",
    "가고싶어", "가고", "주세요", "해줘", "근방", "주변", "부근", "찾아줘",
    "찾아", "가볼만한", "맛있는", "좋고",
    # 한국어 접속조사/어미 — 메뉴로 오탐 방지
    "이나", "에서", "에도", "하고", "이랑", "이랑", "에게", "이며", "이고",
    "하며", "하는", "하면", "에는", "로는", "으로", "부터", "까지",
}


# ── Layer 1 내부 추출 함수 ────────────────────────────────────────

def _extract_station(query: str) -> str | None:
    for st in _STATIONS:
        if st in query:
            return st
        bare = st[:-1] if st.endswith("역") else st
        if bare and bare in query:
            return st
    return None


def _extract_category(query: str) -> str | None:
    for cat in _CATEGORIES:
        if cat in query:
            return cat
    for syn in sorted(_CATEGORY_SYNONYMS, key=len, reverse=True):
        if syn in query:
            return _CATEGORY_SYNONYMS[syn]
    return None


def _extract_facilities(query: str) -> list[str]:
    facilities: list[str] = []
    for syn in sorted(_FACILITY_SYNONYMS, key=len, reverse=True):
        fac = _FACILITY_SYNONYMS[syn]
        if syn in query and fac not in facilities:
            facilities.append(fac)
    return facilities


# 키워드 매칭 허용 접미사: 조사/어미/형용사형 어미
_KW_VALID_SUFFIXES = {
    "가", "이", "은", "는", "을", "를", "와", "과", "도", "로", "에", "의",
    "한", "하다", "해요", "하고", "하며", "하면", "해서", "하니", "하여",
    "이에요", "예요", "아요", "어요",
}


def _kw_token_matches(token: str, word: str) -> bool:
    """token이 word와 정확히 일치하거나, word 뒤에 허용 접미사가 붙은 경우."""
    if token == word:
        return True
    if not token.startswith(word):
        return False
    suffix = token[len(word):]
    return suffix in _KW_VALID_SUFFIXES


def _extract_keywords(query: str) -> list[str]:
    """공백 단위 토큰에서 _KW_REVERSE 키가 허용 접미사와 함께 포함되면 매핑."""
    keywords: list[str] = []
    tokens = query.split()
    for word, kw_name in _KW_REVERSE.items():
        if kw_name in keywords:
            continue
        for token in tokens:
            if _kw_token_matches(token, word):
                keywords.append(kw_name)
                break
    return keywords


def _extract_menu(query: str, consumed: set[str]) -> str | None:
    remaining = query
    for token in consumed:
        remaining = remaining.replace(token, " ")
    candidates = re.findall(r"[가-힣]{2,5}", remaining)
    for c in candidates:
        if c not in _STOP_WORDS_MENU and c not in _KW_REVERSE:
            return c
    return None


# ── Layer 1 ──────────────────────────────────────────────────────

def _layer1(query: str) -> dict:
    station = _extract_station(query)
    category = _extract_category(query)
    facilities = _extract_facilities(query)
    keywords = _extract_keywords(query)

    consumed: set[str] = set()
    if station:
        consumed.add(station)
        consumed.add(station[:-1] if station.endswith("역") else station)
    if category:
        consumed.add(category)
        for syn, cat in _CATEGORY_SYNONYMS.items():
            if syn in query and cat == category:
                consumed.add(syn)
    for syn in _FACILITY_SYNONYMS:
        if syn in query:
            consumed.add(syn)
    for word in _KW_REVERSE:
        if word in query:
            consumed.add(word)

    menu = _extract_menu(query, consumed)

    return {
        "station": station,
        "category": category,
        "menu": menu,
        "keywords": keywords,
        "facilities": facilities,
        "clarification_needed": None,
    }


def _has_anchor(slots: dict) -> bool:
    return bool(slots.get("category") or slots.get("station"))


# ── Layer 2 ──────────────────────────────────────────────────────

_CATEGORIES_STR = ", ".join(_CATEGORIES)
_KW_NAMES_STR = ", ".join(_kw_data.keys())

_LAYER2_SYSTEM = f"""당신은 맛집 검색 슬롯 추출기입니다.
사용자 쿼리에서 아래 JSON 형식으로 슬롯을 추출하세요.
지정된 카테고리·키워드 목록 외의 값은 사용하지 마세요.
JSON만 반환하고 설명은 쓰지 마세요.

카테고리 목록: [{_CATEGORIES_STR}]
리뷰키워드 목록: [{_KW_NAMES_STR}]
시설 목록: [주차, 예약, 포장, 배달]

반환 형식:
{{
  "category": "카테고리명 또는 null",
  "station": "X역 형태 또는 null",
  "menu": "메뉴명 그대로 또는 null",
  "keywords": ["해당 리뷰키워드 목록"],
  "facilities": ["주차/예약/포장/배달 중 해당하는 것들"],
  "clarification_needed": "station이나 category 모두 불명확하면 사용자에게 물을 한 문장(한국어), 아니면 null"
}}"""


def _layer2(query: str, llm_client) -> dict:
    response = llm_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=_LAYER2_SYSTEM,
        messages=[{"role": "user", "content": query}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"station": None, "category": None, "menu": None,
                "keywords": [], "facilities": [], "clarification_needed": None}
    return {
        "station": data.get("station"),
        "category": data.get("category"),
        "menu": data.get("menu"),
        "keywords": data.get("keywords") or [],
        "facilities": data.get("facilities") or [],
        "clarification_needed": data.get("clarification_needed"),
    }


def extract(query: str, llm_client=None) -> dict:
    """자연어 쿼리 → 슬롯 dict.

    Args:
        query: 사용자 입력 문자열
        llm_client: anthropic.Anthropic 인스턴스.
                    None이면 Layer 2 스킵 (테스트·오프라인).

    Returns:
        {
            "category": str | None,
            "station": str | None,
            "menu": str | None,
            "keywords": list[str],
            "facilities": list[str],
            "clarification_needed": str | None,
        }
    """
    slots = _layer1(query)
    if not _has_anchor(slots) and llm_client is not None:
        slots = _layer2(query, llm_client)
    return slots
