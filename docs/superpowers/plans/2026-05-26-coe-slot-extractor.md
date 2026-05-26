# CoE 슬롯 추출기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자 자연어 쿼리를 `kg_search.search()`가 받는 슬롯 dict로 변환하는 `coe/slot_extractor.py` 구현

**Architecture:** Layer 1(정규식/사전, 항상 실행) → anchor 없으면 Layer 2(Claude API, 최대 1회) → 슬롯 dict 반환. 추가 패키지 없이 기존 `anthropic` SDK만 사용.

**Tech Stack:** Python 3.13, anthropic SDK (claude-haiku), pytest, 기존 dicts/ JSON 파일

---

## 파일 구조

| 경로 | 역할 |
|------|------|
| `coe/slot_extractor.py` | 신규 — Layer 1 + Layer 2 + `extract()` 공개 함수 |
| `coe/__init__.py` | 수정 — `extract` re-export |
| `tests/__init__.py` | 신규 — 빈 파일 |
| `tests/coe/__init__.py` | 신규 — 빈 파일 |
| `tests/coe/test_slot_extractor.py` | 신규 — 전체 단위 테스트 |

---

## Task 1: 테스트 인프라 + pytest 설치

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/coe/__init__.py`

- [ ] **Step 1: pytest dev 의존성 추가**

```bash
uv add --dev pytest
```

Expected: `pyproject.toml`에 `[dependency-groups] dev = ["pytest>=..."]` 추가됨

- [ ] **Step 2: 테스트 디렉토리 생성**

```bash
mkdir -p tests/coe
```

Windows PowerShell:
```powershell
New-Item -ItemType Directory -Force tests/coe
```

- [ ] **Step 3: 빈 `__init__.py` 생성**

`tests/__init__.py` — 빈 파일

`tests/coe/__init__.py` — 빈 파일

- [ ] **Step 4: pytest 동작 확인**

```bash
uv run pytest tests/ -v
```

Expected: `no tests ran` (에러 없이 0개 수집)

- [ ] **Step 5: 커밋**

```bash
git add tests/ pyproject.toml uv.lock
git commit -m "chore: add pytest and test directory structure"
```

---

## Task 2: Layer 1 — station + category (TDD)

**Files:**
- Create: `tests/coe/test_slot_extractor.py`
- Create: `coe/slot_extractor.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/coe/test_slot_extractor.py` 생성:

```python
from coe.slot_extractor import _has_anchor, _layer1, extract


# ── station ──────────────────────────────────────────────────────

def test_station_exact():
    assert _layer1("신림역 근처 맛집")["station"] == "신림역"


def test_station_bare():
    # "역" 없이 입력 → 자동 정규화
    assert _layer1("신림 근처 맛집")["station"] == "신림역"


def test_station_long_name():
    assert _layer1("서울대입구역 카페")["station"] == "서울대입구역"


def test_station_none():
    assert _layer1("가성비 좋은 고기집")["station"] is None


# ── category ─────────────────────────────────────────────────────

def test_category_direct():
    assert _layer1("고기집 추천해줘")["category"] == "고기집"


def test_category_synonym():
    assert _layer1("삼겹살집 어디 있어")["category"] == "고기집"


def test_category_none():
    assert _layer1("신림역 근처")["category"] is None
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/coe/test_slot_extractor.py -v
```

Expected: `ImportError: cannot import name '_layer1' from 'coe.slot_extractor'`

- [ ] **Step 3: `coe/slot_extractor.py` 생성 — station + category 구현**

```python
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


def _build_keyword_reverse() -> dict[str, str]:
    reverse: dict[str, str] = {}
    for kw_name, phrases in _kw_data.items():
        for phrase in phrases:
            words = re.findall(r"[가-힣]{2,5}", phrase)
            for word in words:
                if word not in _STOP_WORDS_KW and word not in reverse:
                    reverse[word] = kw_name
    return reverse


_KW_REVERSE: dict[str, str] = _build_keyword_reverse()

# ── 메뉴 불용어 ───────────────────────────────────────────────────

_STOP_WORDS_MENU = {
    "맛집", "추천", "근처", "어디", "좋은", "좋아", "좀", "알려줘", "알려",
    "줘", "어때", "있어", "있는", "없어", "없는", "먹고싶어", "먹고", "싶어",
    "가고싶어", "가고", "주세요", "해줘", "근방", "주변", "부근", "찾아줘",
    "찾아", "가볼만한", "맛있는", "좋고",
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


def _extract_keywords(query: str) -> list[str]:
    keywords: list[str] = []
    for word, kw_name in _KW_REVERSE.items():
        if word in query and kw_name not in keywords:
            keywords.append(kw_name)
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


def extract(query: str, llm_client=None) -> dict:
    """자연어 쿼리 → 슬롯 dict."""
    return _layer1(query)  # Task 4에서 Layer 2 연결 예정
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/coe/test_slot_extractor.py -v -k "station or category"
```

Expected: 7개 PASSED

- [ ] **Step 5: 커밋**

```bash
git add coe/slot_extractor.py tests/coe/test_slot_extractor.py tests/__init__.py tests/coe/__init__.py
git commit -m "feat(coe): Layer 1 station+category extraction"
```

---

## Task 3: Layer 1 — facilities + keywords + menu heuristic (TDD)

**Files:**
- Modify: `tests/coe/test_slot_extractor.py` (테스트 추가)
- Modify: `coe/slot_extractor.py` (이미 구현됨 — 테스트로 검증)

- [ ] **Step 1: 테스트 파일에 facilities/keywords/menu 테스트 추가**

`tests/coe/test_slot_extractor.py` 기존 내용 아래에 추가:

```python
# ── facilities ────────────────────────────────────────────────────

def test_facility_parking():
    assert "주차" in _layer1("주차 되는 식당")["facilities"]


def test_facility_takeout():
    assert "포장" in _layer1("테이크아웃 되나요")["facilities"]


def test_facility_multiple():
    slots = _layer1("주차 예약 가능한 곳")
    assert "주차" in slots["facilities"]
    assert "예약" in slots["facilities"]


def test_facility_none():
    assert _layer1("신림역 고기집")["facilities"] == []


# ── keywords ──────────────────────────────────────────────────────

def test_keyword_gasungbi():
    assert "가격/가성비" in _layer1("가성비 좋은 곳")["keywords"]


def test_keyword_atmosphere():
    assert "분위기/인테리어" in _layer1("분위기 좋은 카페")["keywords"]


def test_keyword_multiple():
    slots = _layer1("분위기 좋고 친절한 식당")
    assert "분위기/인테리어" in slots["keywords"]
    assert "서비스" in slots["keywords"]


def test_keyword_none():
    assert _layer1("신림역 고기집")["keywords"] == []


# ── menu heuristic ────────────────────────────────────────────────

def test_menu_extracted():
    assert _layer1("신림역 냉면 맛집")["menu"] == "냉면"


def test_menu_stopwords_not_extracted():
    # "추천"은 불용어 → menu가 None이어야 함
    assert _layer1("신림역 고기집 추천")["menu"] is None


# ── anchor ────────────────────────────────────────────────────────

def test_has_anchor_station():
    slots = {"station": "신림역", "category": None, "menu": None,
             "keywords": [], "facilities": [], "clarification_needed": None}
    assert _has_anchor(slots)


def test_has_anchor_category():
    slots = {"station": None, "category": "고기집", "menu": None,
             "keywords": [], "facilities": [], "clarification_needed": None}
    assert _has_anchor(slots)


def test_no_anchor():
    slots = {"station": None, "category": None, "menu": None,
             "keywords": [], "facilities": [], "clarification_needed": None}
    assert not _has_anchor(slots)
```

- [ ] **Step 2: 테스트 실행**

```bash
uv run pytest tests/coe/test_slot_extractor.py -v
```

Expected: 모든 테스트 PASSED. 실패 시 `_extract_*` 함수 디버그:
- facility 실패: `_FACILITY_SYNONYMS` 키 확인
- keyword 실패: `_KW_REVERSE` 빌드 결과 확인 (`python -c "from coe.slot_extractor import _KW_REVERSE; print(_KW_REVERSE)"`)
- menu 실패: `_STOP_WORDS_MENU`에 해당 단어 추가

- [ ] **Step 3: 커밋**

```bash
git add tests/coe/test_slot_extractor.py
git commit -m "test(coe): Layer 1 facilities+keywords+menu tests pass"
```

---

## Task 4: Layer 2 — Claude API 슬롯 추출 (TDD)

**Files:**
- Modify: `tests/coe/test_slot_extractor.py` (Layer 2 테스트 추가)
- Modify: `coe/slot_extractor.py` (`_layer2()` 구현 + `extract()` 라우팅 완성)

- [ ] **Step 1: Layer 2 + extract() 테스트 추가**

`tests/coe/test_slot_extractor.py` 아래에 추가:

```python
from unittest.mock import MagicMock


# ── extract(): anchor 있으면 Layer 2 호출 안 함 ──────────────────

def test_extract_no_llm_call_when_anchor():
    mock_client = MagicMock()
    result = extract("신림역 고기집", llm_client=mock_client)
    mock_client.messages.create.assert_not_called()
    assert result["station"] == "신림역"
    assert result["category"] == "고기집"


# ── extract(): anchor 없으면 Layer 2 호출 ────────────────────────

def test_extract_calls_llm_when_no_anchor():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"category": "고기집", "station": "신림역", "menu": null, '
             '"keywords": [], "facilities": [], "clarification_needed": null}'
    )]
    mock_client.messages.create.return_value = mock_response

    result = extract("가성비 좋은 곳", llm_client=mock_client)
    mock_client.messages.create.assert_called_once()
    assert result["category"] == "고기집"


# ── extract(): llm_client=None이면 Layer 2 스킵 ──────────────────

def test_extract_skips_layer2_when_no_client():
    result = extract("가성비 좋은 곳", llm_client=None)
    assert result["station"] is None
    assert result["category"] is None


# ── extract(): clarification_needed 필드 전달 ────────────────────

def test_extract_clarification_needed_passed_through():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"category": null, "station": null, "menu": null, '
             '"keywords": [], "facilities": [], '
             '"clarification_needed": "어느 지역에서 찾으세요?"}'
    )]
    mock_client.messages.create.return_value = mock_response

    result = extract("맛있는 거 먹고싶어", llm_client=mock_client)
    assert result["clarification_needed"] == "어느 지역에서 찾으세요?"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/coe/test_slot_extractor.py -v -k "extract"
```

Expected: FAILED (`extract()` 내부에서 Layer 2 미호출)

- [ ] **Step 3: `coe/slot_extractor.py`에 `_layer2()` 추가 + `extract()` 라우팅 완성**

`_has_anchor()` 함수 아래에 `_layer2()` 추가:

```python
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
    data = json.loads(raw)
    return {
        "station": data.get("station"),
        "category": data.get("category"),
        "menu": data.get("menu"),
        "keywords": data.get("keywords") or [],
        "facilities": data.get("facilities") or [],
        "clarification_needed": data.get("clarification_needed"),
    }
```

기존 `extract()` 함수 교체:

```python
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
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
uv run pytest tests/coe/test_slot_extractor.py -v
```

Expected: 전체 PASSED (24개 이상)

- [ ] **Step 5: 커밋**

```bash
git add coe/slot_extractor.py tests/coe/test_slot_extractor.py
git commit -m "feat(coe): Layer 2 Claude API slot extraction + extract() routing"
```

---

## Task 5: coe/__init__.py export + 손검증 스크립트

**Files:**
- Modify: `coe/__init__.py`
- Create: `scripts/verify_coe.py`

- [ ] **Step 1: `coe/__init__.py`에 `extract` export**

```python
from coe.slot_extractor import extract

__all__ = ["extract"]
```

- [ ] **Step 2: 손검증 스크립트 작성**

`scripts/verify_coe.py` 생성:

```python
"""
CoE 슬롯 추출 손검증 스크립트.

실행:
    python scripts/verify_coe.py
"""

import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from coe.slot_extractor import extract

load_dotenv(Path(__file__).parent.parent / ".env")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def show(label: str, query: str, use_llm: bool = False):
    slots = extract(query, llm_client=client if use_llm else None)
    print(f"\n{'='*55}")
    print(f"[{label}]")
    print(f"  입력: {query!r}")
    print(f"  station  : {slots['station']}")
    print(f"  category : {slots['category']}")
    print(f"  menu     : {slots['menu']}")
    print(f"  keywords : {slots['keywords']}")
    print(f"  facilities: {slots['facilities']}")
    if slots["clarification_needed"]:
        print(f"  ※ 되묻기  : {slots['clarification_needed']}")


# Layer 1만
show("역+카테고리", "신림역 근처 고기집 추천해줘")
show("역+메뉴", "서울대입구역 냉면 먹고싶어")
show("가성비+분위기", "가성비 좋고 분위기 좋은 카페")
show("시설", "주차 되고 예약 가능한 식당")
show("동의어", "삼겹살집 어디 좋아?")

# Layer 2 (anchor 없음 → LLM 호출)
show("anchor 없음 (LLM)", "오늘 저녁 뭐 먹지?", use_llm=True)
show("anchor 없음 (LLM)", "분위기 좋은 데이트 코스", use_llm=True)
```

- [ ] **Step 3: 손검증 실행 (Neo4j 불필요, ANTHROPIC_API_KEY만 있으면 됨)**

```bash
$env:PYTHONIOENCODING = "utf-8"
uv run python scripts/verify_coe.py
```

Expected 예시:
```
[역+카테고리]
  입력: '신림역 근처 고기집 추천해줘'
  station  : 신림역
  category : 고기집
  menu     : None
  keywords : []
  facilities: []
```

anchor 없는 케이스에서 `clarification_needed`에 한국어 문장 출력되면 성공.

- [ ] **Step 4: 전체 테스트 재확인**

```bash
uv run pytest tests/ -v
```

Expected: 전체 PASSED

- [ ] **Step 5: 커밋**

```bash
git add coe/__init__.py scripts/verify_coe.py
git commit -m "feat(coe): export extract(), add verify_coe.py script"
```

---

## 완료 기준

- [ ] `uv run pytest tests/coe/test_slot_extractor.py -v` 전체 통과
- [ ] `python scripts/verify_coe.py` 실행 시 역+카테고리 케이스 슬롯 정상 추출
- [ ] anchor 없는 케이스에서 LLM 호출 + clarification_needed 문장 출력
- [ ] TODO.md 단계 B 항목 업데이트
