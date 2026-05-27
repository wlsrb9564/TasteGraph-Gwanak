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
from coe import extract

load_dotenv(Path(__file__).parent.parent / ".env")
_api_key = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=_api_key) if _api_key else None


def show(label: str, query: str, use_llm: bool = False):
    if use_llm and client is None:
        print(f"\n[{label}] 스킵 — ANTHROPIC_API_KEY 없음")
        return
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


# Layer 1만 (LLM 없음)
show("역+카테고리", "신림역 근처 고기집 추천해줘")
show("역+메뉴", "서울대입구역 냉면 먹고싶어")
show("가성비+분위기", "가성비 좋고 분위기 좋은 카페")
show("시설", "주차 되고 예약 가능한 식당")
show("동의어", "삼겹살집 어디 좋아?")

# Layer 2 (anchor 없음 → LLM 호출)
show("anchor 없음 (LLM)", "오늘 저녁 뭐 먹지?", use_llm=True)
show("anchor 없음 (LLM)", "분위기 좋은 데이트 코스", use_llm=True)
