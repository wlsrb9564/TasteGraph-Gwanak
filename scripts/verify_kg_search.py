"""
KG 검색 손검증 스크립트.

실행:
    python scripts/verify_kg_search.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).parent.parent))
from kg.kg_search import search

load_dotenv(Path(__file__).parent.parent / ".env")
driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
)


def show(label, res):
    print(f"\n{'='*50}")
    print(f"[{label}]  radius_used={res['radius_used']}  n={len(res['candidates'])}")
    print(f"{'='*50}")
    for c in res["candidates"]:
        dist = f"{round(c['dist'])}m" if c["dist"] is not None else "-"
        menu = f"  matched={c['matched_menu']}({c['matched_menu_price']}원)" if c["matched_menu"] else ""
        sigs = [s["name"] for s in (c["signature_menus"] or [])[:3]]
        print(f"  {c['name']:<22} {dist:<8} 리뷰 {c['visitor_reviews']}{menu}")
        if sigs:
            print(f"    signature: {', '.join(sigs)}")


# 패턴 ① 지역/역 + 카테고리
show("패턴① 고기집+서울대입구역",
     search(driver, {"category": "고기집", "station": "서울대입구역", "radius": 500}))

# 패턴 ② 메뉴 검색 단독
show("패턴② 냉면+신림역",
     search(driver, {"menu": "냉면", "station": "신림역"}))

# 패턴 ① + ② 조합
show("패턴①+② 한식+된장찌개+낙성대역",
     search(driver, {"category": "한식", "menu": "된장찌개", "station": "낙성대역"}))

# 패턴 ③ 키워드 단일
show("패턴③ 가격/가성비+서울대입구역",
     search(driver, {"keywords": ["가격/가성비"], "station": "서울대입구역"}))

# 패턴 ③ 복수 키워드 AND
show("패턴③ 복수키워드(가격/가성비+분위기/인테리어)+신림역",
     search(driver, {"keywords": ["가격/가성비", "분위기/인테리어"], "station": "신림역"}))

# 패턴 ②+③ 조합
show("패턴②+③ 삼겹살+가격/가성비+신림역",
     search(driver, {"menu": "삼겹살", "keywords": ["가격/가성비"], "station": "신림역"}))

# 패턴 ④ 시설 단독
show("패턴④ 주차+예약+서울대입구역",
     search(driver, {"facilities": ["주차", "예약"], "station": "서울대입구역"}))

# 패턴 ③+④ 조합
show("패턴③+④ 가격/가성비+주차+신림역",
     search(driver, {"keywords": ["가격/가성비"], "facilities": ["주차"], "station": "신림역"}))

# 패턴 ②+③+④ 전체 조합
show("패턴②+③+④ 삼겹살+가격/가성비+주차+신림역",
     search(driver, {"menu": "삼겹살", "keywords": ["가격/가성비"], "facilities": ["주차"], "station": "신림역"}))

# 위치 없을 때 graceful degradation
show("위치없음 카테고리만",
     search(driver, {"category": "카페"}))

driver.close()
