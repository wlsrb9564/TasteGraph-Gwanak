# CLAUDE.md — 관악구 맛집 추천 서비스

> Claude Code가 매 세션 자동으로 읽는 프로젝트 컨텍스트.
> 이 레포는 **서비스 코드**다. 데이터(그래프)는 별도로 돌아가는 Neo4j에 있다.

---

## 0. 한 줄 요약

자연어 질문 → **CoE**(슬롯 추출) → **KG 검색**(Cypher) → **LLM**(자연어 추천).
DB 구축은 끝났고, 지금은 이 검색/추천 로직을 구현하는 단계다.

```
[Neo4j 컨테이너]  ← 항상 떠있는 데이터 보관소 (이 레포에 데이터 없음)
       ↑ bolt 접속 (neo4j://localhost:7687)
[이 레포]  ← CoE → KG검색 → LLM
```

---

## 1. 환경

- **Neo4j**: `docker compose up -d` (data/ 볼륨 마운트, 재적재 불필요)
- **Python**: `uv sync` → `.venv` 생성. 의존성은 `pyproject.toml`.
- **시크릿**: `.env` 파일. NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD / ANTHROPIC_API_KEY.
- **데이터**: 관악구 단일 지역, 식당 4198건. (City/District 필터는 현재 변별력 없음 — 정상)

---

## 2. 그래프 스키마 (확정)

### 노드
- **Restaurant** — `place_id`(unique), `name`, `lat`, `lng`, `location`(point), `address`,
  `visitor_review_count`, `blog_review_count`, `review_participant_count`,
  `affordable`, `has_sns`, `has_menu_data`
- **Category**(15) / **District** / **City** — `name`
- **Menu** — `name` (원본 메뉴명, **정규화 안 함**)
- **MenuKeyword** — `name` (리뷰 언급 메뉴)
- **ReviewKeyword**(11) — `name`
- **Facility** — `name`

### 관계 (괄호=관계속성)
- `(Restaurant)-[:IN_CATEGORY]->(Category)`
- `(Restaurant)-[:LOCATED_IN]->(District)`
- `(Restaurant)-[:LOCATED_IN_CITY]->(City)`
- `(Restaurant)-[:HAS_MENU {price, is_representative}]->(Menu)`
- `(Restaurant)-[:MENTIONED_AS {count, ratio}]->(MenuKeyword)`
- `(Restaurant)-[:HAS_REVIEW_KEYWORD {ratio, weight}]->(ReviewKeyword)`
- `(Restaurant)-[:OFFERS]->(Facility)`

> `r.location`은 거리검색용 point. 공간 인덱스 `restaurant_location_idx` 존재.
> 4198건 중 4195건에 location 있음(좌표 없던 3건은 정상 제외).

### 15 카테고리
한식 / 고기집 / 닭요리 / 찌개/탕/국 / 해산물요리 / 면/만두 / 분식 / 일식 / 중식 / 세계음식 / 양식 / 술집 / 카페 / 베이커리 / 기타/유통/제조

### 11 리뷰키워드
맛 / 재료/품질 / 가격/가성비 / 양/구성 / 서비스 / 분위기/인테리어 / 청결/시설 / 상황/목적 / 비주얼 / 접근성 / 상품

---

## 3. 프로젝트 구조

```
TasteGraph-Gwanak/
├── kg/             # 단계 A: KG 검색 (kg_search.py — 빌더 + 어셈블러)
├── coe/            # 단계 B: 슬롯 추출 (정규식·사전·동의어)
├── llm/            # 단계 C: LLM 출구 프롬프트·API 호출
├── dicts/          # KG 노드명 사전 (category_mapping, keyword_categories, station_coords)
├── scripts/        # 손검증 스크립트 (verify_kg_search.py 등)
├── etl/            # 전처리·적재 노트북 (1회성, 재실행 불필요)
├── data/           # Neo4j 볼륨 (git 제외)
└── pipeline.py     # CoE → KG → LLM 연결 + 폴백·되묻기
```

- 역 좌표는 `dicts/station_coords.json`에서 관리. `kg_search.py`가 런타임에 로드.
- 슬롯 dict → `kg.kg_search.search(driver, slots)` 한 함수로 모든 패턴 처리.

---

## 4. 거리 검색 규칙

- 검색 기준점: 역 좌표 / 사용자 현재 위치 모두 `$lat/$lng`에 넣으면 동일 동작.
- **거리 하드컷은 빈 결과 위험** → 반경 점진 확장 폴백 필수:
  **500 → 800 → 1200 → 1800m**, 후보 K개 채울 때까지.
- 실제 사용 반경(`radius_used`)은 반환값에 포함 → LLM 맥락으로 활용.

---

## 5. ⚠️ 핵심 주의사항

1. **메뉴 검색은 Menu CONTAINS가 주.** MenuKeyword는 signature 메뉴 표시용 보조(ratio, 표본 ≥20).
2. **ratio는 1.0을 초과할 수 있다.** "1인당 평균 언급 강도". 식당 간 비교 부적합.
   - **식당 간 vibe 비교는 `weight`(식당 내 정규화, 합=1)로.**
3. **LLM 출구에서 ratio/weight를 퍼센트 단언으로 쓰지 말 것.** "참여자 X%가~"(❌) → "언급이 특히 많아요"(⭕).
4. **LLM은 KG에 명시된 근거만 사용, 추측 금지.** 후보에 없는 메뉴·시설 지어내기 금지.
5. **dicts는 KG 노드명과 동기화 유지.** 노드명은 `/` 사용 (가격/가성비, 찌개/탕/국 등).
6. **표본 작은 식당 주의.** ReviewKeyword/MenuKeyword 정렬 시 `review_participant_count >= 20`.
7. **LLM 호출은 파이프라인당 최대 2회** — anchor 없을 때 되묻기 1 + 출구 1. 매칭·폴백·정렬은 전부 코드/Cypher로.

---

## 6. 코딩 컨벤션

- 슬롯은 dict로 주고받음. **슬롯에 있는 것만** 동적으로 MATCH/WHERE 조립.
- 빌더 함수(`_build_*_block`)가 Cypher 조각 dict 반환 → `search()` 어셈블러가 병합.
- 검색 폴백 2단계: **strict**(조건 다 걸기) → **loose**(keyword/facility 완화). anchor(역·카테고리)는 유지.
- 손검증은 `scripts/` 폴더 스크립트로. 운영 코드에 `__main__` 블록 두지 말 것.
