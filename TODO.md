# TODO — 관악구 맛집 추천 서비스

## 현재 위치

```
[전처리·적재·좌표 point] ✅ 완료 (etl/)
        ↓
[단계 A: KG 검색] ✅ 완료 (strict→loose 폴백 제외)
        ↓
[단계 B: CoE 슬롯추출] 🔵 다음 ← 지금 여기
[단계 C: LLM 출구] ⬜
[단계 D: 파이프라인 연결] ⬜
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
- [ ] strict → loose 폴백 — anchor(역·카테고리) 유지하고 keyword/facility 완화

## 단계 B — CoE (슬롯 추출) 🔵

사용자 자연어 → 슬롯 dict (입구).

- [x] 사전 파일 준비: `dicts/category_mapping.json`, `keyword_categories.json`, `station_coords.json`
- [ ] 정규식/사전 매칭으로 카테고리·키워드·시설 슬롯 추출 (`coe/`)
- [ ] 역 이름 → 좌표 변환 + 역 동의어 ("신림"→"신림역")
- [ ] 시설 동의어 ("차 가져가도 돼?"→주차, "테이크아웃"→포장)
- [ ] anchor(지역·역·카테고리) 없으면 LLM으로 1회만 되묻기

## 단계 C — LLM 출구

후보 + 근거(weight, count, dist) → 자연어 추천.

- [ ] 출구 프롬프트 작성 (근거만 사용, 추측 금지)
- [ ] ratio/weight 퍼센트 단언 금지 가드
- [ ] `radius_used`를 맥락으로 활용 ("조금 넓게 봤어요")
- [ ] LLM API 호출 모듈 (`llm/`), 키는 환경변수

## 단계 D — 파이프라인 연결

- [ ] `pipeline.py`: CoE → KG → LLM 통합
- [ ] 폴백·되묻기 흐름 (LLM 호출 최대 2회)
- [ ] end-to-end 테스트: 자연어 한 줄 넣고 추천 문장 받기
