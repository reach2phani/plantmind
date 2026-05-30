"""Minimal test to find exact failing Cypher"""
import os, sys
from dotenv import load_dotenv
load_dotenv()

uri = os.getenv("NEO4J_URI","").replace("neo4j+s://","bolt+ssc://")
user = os.getenv("NEO4J_USERNAME","neo4j")
pwd = os.getenv("NEO4J_PASSWORD","")

from neo4j import GraphDatabase
driver = GraphDatabase.driver(uri, auth=(user,pwd))

tests = [
    ("Simple RETURN", "RETURN 1 as n", {}),
    ("Simple MATCH", "MATCH (n) RETURN count(n) as c", {}),
    ("MATCH with WHERE", "MATCH (n) WHERE n.equip_tag = $e DETACH DELETE n", {"e":"WM-101"}),
    ("MERGE simple", "MERGE (n:Test {_id: 'test1'}) SET n.name='test' RETURN n", {}),
    ("DELETE test", "MATCH (n:Test) DETACH DELETE n", {}),
]

with driver.session() as session:
    for name, cypher, params in tests:
        try:
            session.run(cypher, params).consume()
            print(f"  OK: {name}")
        except Exception as e:
            print(f"  FAIL: {name}")
            print(f"    Error: {e}")

driver.close()
print("Done")
