# 관악구 맛집 추천 서비스

Neo4j 지식그래프 기반 맛집 추천. 자연어 질문을 받아 슬롯으로 분해(CoE)하고,
그래프를 검색(KG)한 뒤, 근거 기반으로 자연어 추천을 생성(LLM)한다.

```
자연어 질문 → CoE(슬롯추출) → KG검색(Cypher) → LLM(추천) → 추천 문장
```

> 이 레포는 **서비스 코드**다. 데이터는 별도 Neo4j 컨테이너에 있다.
> 프로젝트 전반 컨텍스트는 `CLAUDE.md`, 작업 목록은 `TODO.md` 참고.

---

## 사전 준비

### 1. 가상환경 & 패키지 (uv)

```bash
# uv 없으면 먼저 설치
pip install uv

# 가상환경 생성 + 패키지 설치 (한 번에)
uv sync

# 가상환경 활성화
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

의존성 목록은 `pyproject.toml`에 관리. 패키지 추가 시: `uv add <패키지명>`

### 2. 환경변수

```bash
cp .env.example .env
# .env 파일을 열어 실제 값으로 채우기
```

`.env` 파일:
```
NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
ANTHROPIC_API_KEY=sk-ant-...
```

> `.env`는 `.gitignore`에 포함 — 커밋되지 않음.

### 3. Neo4j 실행 (Docker Compose)

데이터가 담긴 볼륨(`data/`)을 마운트해서 구동. **데이터는 이미 적재 완료 — 재적재 불필요.**

```bash
docker compose up -d
```

- Bolt: `neo4j://localhost:7687`
- Browser UI: http://localhost:7474

중지/재시작: `docker compose stop` / `docker compose start`

---

## 프로젝트 구조

```
TasteGraph-Gwanak/
├── kg/             # 단계 A: KG 검색 (kg_search.py)
├── coe/            # 단계 B: 슬롯 추출 (정규식·사전·동의어)
├── llm/            # 단계 C: LLM 출구 프롬프트·API 호출
├── dicts/          # KG 노드명 사전 (category_mapping, keyword_categories, station_coords)
├── scripts/        # 손검증 스크립트
├── etl/            # 전처리·적재 노트북 (1회성, 재실행 불필요)
├── data/           # Neo4j 볼륨 (git 제외, 로컬 보관)
├── pipeline.py     # CoE → KG → LLM 연결 + 폴백·되묻기
├── pyproject.toml  # 의존성 (uv 관리)
├── docker-compose.yml
└── .env            # 시크릿 (git 제외, .env.example 참고)
```

---

## 빠른 확인

KG 검색 손검증 스크립트 실행:

```bash
python scripts/verify_kg_search.py
```

또는 직접 슬롯 넣어 확인:

```python
from kg.kg_search import search

# 패턴 ① 역 + 카테고리
search(driver, {"category": "고기집", "station": "서울대입구역"})

# 패턴 ② 메뉴
search(driver, {"menu": "냉면", "station": "신림역"})

# 패턴 ③ 리뷰키워드
search(driver, {"keywords": ["가격/가성비"], "station": "낙성대역"})

# 패턴 ④ 시설
search(driver, {"facilities": ["주차", "예약"], "station": "서울대입구역"})

# 조합 (슬롯 있는 것만 자동 조립)
search(driver, {"category": "한식", "menu": "된장찌개", "keywords": ["양/구성"], "station": "봉천역"})
```

---

## 데이터 개요

- 관악구 단일 지역, 식당 4198건
- 노드: Restaurant / Category(15) / Menu / MenuKeyword / ReviewKeyword(11) / Facility / District / City
- 스키마·주의사항 전체는 `CLAUDE.md` 참고
