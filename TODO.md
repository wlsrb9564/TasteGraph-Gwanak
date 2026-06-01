# TODO — 관악구 맛집 추천 서비스

## 현재 위치

```
[전처리·적재·좌표 point] ✅ 완료 (etl/)
        ↓
[단계 A: KG 검색] ✅ 완료
        ↓
[단계 B: CoE 슬롯추출] ✅ 완료
        ↓
[단계 C: LLM 출구] ✅ 완료
        ↓
[단계 D: 파이프라인 연결] ✅ 완료
```

---

## 단계 A — KG 검색 함수 ✅

슬롯 dict → 후보 식당 리스트. `kg/kg_search.py`

- [x] 패턴 ① 지역/역 + 카테고리 (거리검색)
  - [x] 슬롯 동적 조립 (빌더 + 어셈블러 패턴)
  - [x] 거리 폴백 사다리 500→800→1200→1800
  - [x] 위치 없을 때 graceful degradation (리뷰순)
  - [x] 손검증 (`scripts/verify_kg_search.py`)
- [x] 패턴 ② 구체메뉴 (Menu CONTAINS, 표본 ≥20 필터)
- [x] 패턴 ③ 분위기/특징 (ReviewKeyword `weight` 가중, 복수 AND)
- [x] 패턴 ④ 시설 필터 (OFFERS, 복수 AND)
- [x] strict → loose 폴백 — anchor(역·카테고리) 유지하고 keyword/facility 완화
  - `LOOSE_MIN_RESULTS = 3` 미만이면 keyword/facility 제거 후 재시도
  - 반환값에 `search_mode: "strict" | "loose"` 포함

## 단계 B — CoE (슬롯 추출) ✅

사용자 자연어 → 슬롯 dict (입구). `coe/slot_extractor.py`

- [x] 사전 파일 준비: `dicts/category_mapping.json`, `keyword_categories.json`, `station_coords.json`
- [x] Layer 1 — 정규식/사전 매칭 (LLM 없음, 항상 실행)
  - [x] 역 이름 추출 + 동의어 정규화 ("신림"→"신림역")
  - [x] 카테고리 추출 + 동의어 ("삼겹살집"→"고기집" 등)
  - [x] 시설 동의어 ("테이크아웃"→포장, "주차장"→주차 등)
  - [x] 키워드 추출 (형태소 어근 매칭, 토큰 경계 허용 접미사)
  - [x] 메뉴 잔여 명사 휴리스틱 (소비된 토큰 제거 후 2~5자 한글)
- [x] Layer 2 — Claude API 슬롯 추출 (anchor 없을 때만, 최대 1회)
  - anchor = station 또는 category 중 하나 이상 존재
  - `clarification_needed` 필드: station·category 모두 불명확하면 되묻기 문장 반환
  - 모델: `claude-haiku-4-5-20251001`
- [x] 손검증 (`scripts/verify_coe.py`)

## 단계 C — LLM 출구 ✅

후보 + 근거(weight, count, dist) → 자연어 추천. `llm/exit.py`

- [x] 출구 프롬프트 작성 (KG 명시 근거만 사용, 추측 금지)
- [x] ratio/weight 퍼센트 단언 금지 가드 ("참여자 X%가~" ❌)
- [x] `radius_used` + `search_mode` 맥락으로 LLM에 전달
- [x] `review_participant_count` 포함 → 표본 작은 식당 주의 rule 적용 가능
- [x] LLM API 호출 모듈 (`llm/`), 키는 환경변수
  - 빈 후보 → LLM 없이 "죄송해요" 문자열 반환
  - `llm_client=None` → 후보 이름 목록 반환 (오프라인 폴백)
  - API 예외 → try/except로 항상 str 반환 보장
  - 모델: `claude-haiku-4-5-20251001`, max_tokens=512

## 단계 D — 파이프라인 연결 ✅

- [x] `pipeline.py`: CoE → KG → LLM 통합
  - `run(query, driver, llm_client=None) -> str`
  - 되묻기: `clarification_needed` 있으면 KG/LLM 호출 없이 바로 반환
- [x] LLM 호출 최대 2회 보장 (CoE Layer 2 + LLM 출구)
- [x] 단위 테스트: 전체 흐름 mock 기반 검증 (`tests/test_pipeline.py`)
  - 되묻기 단락, anchor 경로, no-anchor LLM 경로, 빈 후보 통과, 항상 str 반환
