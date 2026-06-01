"""
전체 파이프라인 손검증 스크립트.

실행:
    uv run python scripts/verify_pipeline.py
"""

import os
import sys
from pathlib import Path

import anthropic
import neo4j
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
import pipeline

load_dotenv(Path(__file__).parent.parent / ".env")

driver = neo4j.GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
)
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def ask(label: str, query: str):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    print(f"질문: {query}")
    print("-" * 60)
    result = pipeline.run(query, driver, client)
    print(result)


# ── Layer 1 anchor → KG 검색 + LLM 출구 ──────────────────────────

# 역 + 카테고리 + 키워드 복합
ask("역+카테고리+가성비",
    "신림역 근처 가성비 좋고 양 많은 고기집 추천해줘")

# 역 + 카테고리 + 시설 복합
ask("역+카테고리+시설",
    "서울대입구역 주차 되고 예약 가능한 한식집 알려줘")

# 동의어 + 시설 복합
ask("동의어+시설",
    "낙성대역 근처 테이크아웃 되는 커피숍 어디 있어?")

# 역 + 구체 메뉴
ask("역+구체메뉴",
    "봉천역 냉면 먹고 싶은데 어디 가면 돼?")

# 역 + 분위기 키워드 + 카테고리
ask("역+분위기+카테고리",
    "신림역 분위기 좋고 인테리어 예쁜 카페 추천해줘")

# 역 + 다중 키워드
ask("역+다중키워드",
    "서울대입구역 근처에서 맛도 좋고 친절하고 청결한 식당 알려줘")

# 동의어 카테고리 + 시설 + 키워드
ask("동의어카테고리+복합조건",
    "신림역 삼겹살집인데 주차 되고 가성비 좋은 곳")

# ── anchor 없음 → CoE Layer 2 LLM 호출 ───────────────────────────

# 상황 기반 (지역 불명확)
ask("상황기반(LLM)",
    "회식 장소 찾는데 단체로 고기 먹기 좋은 데 어디야?")

# 감성 기반 (카테고리 불명확)
ask("감성기반(LLM)",
    "비 오는 날 따뜻하게 먹을 수 있는 국물 요리 맛집")

# 완전 모호 (되묻기 유도)
ask("완전모호→되묻기(LLM)",
    "맛있는 거 먹고 싶어")

driver.close()
