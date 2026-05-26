# CoE 슬롯 추출기 설계 — 단계 B

**날짜:** 2026-05-26
**대상 파일:** `coe/slot_extractor.py`

---

## 1. 목적

사용자 자연어 쿼리를 `kg_search.search()`가 받는 슬롯 dict로 변환한다.

```
"신림역 근처 가성비 좋은 고기집" → {"station": "신림역", "category": "고기집", "keywords": ["가격/가성비"]}
```

---

## 2. 아키텍처 — 2계층 구조

```
사용자 쿼리 (str)
        ↓
┌─────────────────────────────────────┐
│  Layer 1 — 코드만 (항상 실행)        │
│  station / category / keywords /    │
│  facilities / menu(heuristic)       │
└──────────────┬──────────────────────┘
               │
        anchor 있음?
     (category OR station)
        ↙           ↘
      YES             NO
       │               ↓
       │    ┌──────────────────────────┐
       │    │  Layer 2 — Claude API    │
       │    │  (조건부, 최대 1회)       │
       │    │  JSON 슬롯 추출 전체      │
       │    │  clarification_needed    │
       │    └──────────┬───────────────┘
       └───────────────┘
                ↓
          slots dict 반환
```

**LLM 호출 예산 (파이프라인 전체):**
- Layer 2 (CoE): 0~1회 (anchor 없을 때만)
- LLM 출구 (추천 생성): 1회
- 합계: 최대 2회

---

## 3. Layer 1 — 슬롯별 추출 규칙

### 3-1. station

- 소스: `dicts/station_coords.json` 키 목록 (런타임 로드)
- 규칙: 쿼리에 "X역" 포함 → `"X역"` / "X" 포함 → `"X역"`으로 정규화
- 예: "신림" → "신림역", "서울대입구역" → "서울대입구역"

### 3-2. category

- 소스: `dicts/category_mapping.json` 키 15개 + 코드 내 소형 동의어 dict
- 규칙: KG 카테고리명 직접 매칭 우선, 동의어 보조
- 동의어 예시: "삼겹살집" → 고기집, "커피숍" → 카페, "라멘" → 면/만두
- `category_mapping.json`의 값(네이버 업종코드)은 CoE에서 사용하지 않음 — ETL 전용

### 3-3. keywords

- 소스: `dicts/keyword_categories.json` 값에서 핵심 단어 자동 추출 (별도 사전 불필요)
- 규칙: 각 리뷰 문구에서 핵심 명사 추출 → 역방향 dict 생성
- 예: "가성비" → 가격/가성비, "분위기" → 분위기/인테리어, "청결" → 청결/시설
- 복수 매칭 허용

### 3-4. facilities

- 소스: `coe/slot_extractor.py` 내 소형 dict (하드코딩)
- 매핑:

| 사용자 표현 | KG Facility 노드명 |
|-------------|-------------------|
| 주차, 주차장, 차 가져가 | 주차 |
| 예약 | 예약 |
| 포장, 테이크아웃, 포장주문 | 포장 |
| 배달, 배달가능 | 배달 |

### 3-5. menu (residual heuristic)

- 규칙: station/category/keywords/facilities 매칭 후 남은 토큰 중 2~5자 한글 명사
- 불용어 제거: "맛집", "추천", "근처", "어디", "좋은", "좀", "알려줘" 등
- 오탐 가능성 있으나 anchor가 있으면 KG 검색에서 자동 보정됨

---

## 4. Layer 2 — Claude API 슬롯 추출

### 트리거 조건

Layer 1 결과에서 `category`와 `station` 모두 None인 경우.

### 모델

`claude-haiku-4-5-20251001` — CoE 슬롯 추출은 빠른 모델로 충분

### 프롬프트 구조

```
[시스템]
당신은 맛집 검색 슬롯 추출기입니다.
사용자 쿼리에서 아래 JSON 형식으로 슬롯을 추출하세요.
지정된 카테고리·키워드 목록 외의 값은 사용하지 마세요.
JSON만 반환하고 설명은 쓰지 마세요.

카테고리 목록: [한식, 고기집, 닭요리, 찌개/탕/국, 해산물요리, 면/만두,
               분식, 일식, 중식, 세계음식, 양식, 술집, 카페, 베이커리, 기타/유통/제조]
리뷰키워드 목록: [맛, 재료/품질, 가격/가성비, 양/구성, 서비스,
                분위기/인테리어, 청결/시설, 상황/목적, 비주얼, 접근성, 상품]

[유저]
"{query}"

[기대 출력]
{
  "category": "카테고리명 또는 null",
  "station": "X역 형태 또는 null",
  "menu": "메뉴명 그대로 또는 null",
  "keywords": ["해당 리뷰키워드 목록"],
  "facilities": ["주차/예약/포장/배달 등"],
  "clarification_needed": "station이나 category 모두 불명확하면 사용자에게 물을 한 문장, 아니면 null"
}
```

### clarification_needed 처리

- `null`: 슬롯 충분 → 바로 `kg_search.search()` 호출
- 문자열: 파이프라인이 사용자에게 해당 문장 출력 → 응답 받아 `extract()` 재호출 (1회 한정)

---

## 5. 공개 인터페이스

```python
# coe/slot_extractor.py

def extract(query: str, llm_client=None) -> dict:
    """
    자연어 쿼리 → 슬롯 dict

    Args:
        query: 사용자 입력 문자열
        llm_client: anthropic.Anthropic 인스턴스.
                    None이면 Layer 2 스킵 (테스트·오프라인 용)

    Returns:
        {
            "category": str | None,
            "station": str | None,
            "menu": str | None,
            "keywords": list[str],       # 빈 리스트 가능
            "facilities": list[str],     # 빈 리스트 가능
            "clarification_needed": str | None,
        }
    """
```

---

## 6. 파일 구조

```
coe/
├── __init__.py          # 기존 (빈 파일)
└── slot_extractor.py    # Layer 1 + Layer 2 단일 파일
```

단일 파일로 관리. 함수 분리 기준:
- `_layer1(query) -> dict` — 코드 전용
- `_layer2(query, llm_client) -> dict` — Claude API 호출
- `extract(query, llm_client) -> dict` — 외부 공개 진입점

---

## 7. 의존성

추가 패키지 없음. `pyproject.toml`에 이미 있는 것만 사용:
- `anthropic` — Layer 2 LLM 호출
- `python-dotenv` — ANTHROPIC_API_KEY 로드 (pipeline.py에서 처리)
