"""Facility 데이터 파악용 임시 스크립트."""
import os
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(Path(__file__).parent.parent / ".env")
driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))

with driver.session() as s:
    print("=== Facility 노드 전체 목록 + 연결 식당 수 ===")
    res = s.run("""
        MATCH (f:Facility)<-[:OFFERS]-(r:Restaurant)
        RETURN f.name AS facility, count(r) AS restaurant_count
        ORDER BY restaurant_count DESC
    """)
    for row in res:
        print(f"  '{row['facility']}'  식당 수: {row['restaurant_count']}")

    print("\n=== 식당 하나의 Facility 목록 예시 ===")
    res = s.run("""
        MATCH (r:Restaurant)-[:OFFERS]->(f:Facility)
        WITH r, collect(f.name) AS facilities
        WHERE size(facilities) >= 3
        RETURN r.name AS name, facilities LIMIT 3
    """)
    for row in res:
        print(f"  {row['name']}: {row['facilities']}")

driver.close()
