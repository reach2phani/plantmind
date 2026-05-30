"""
Final test — uses neo4j+ssc:// which showed SUCCESS in try_all.py
and runs a full load test
"""
import os, json
from dotenv import load_dotenv
load_dotenv(override=True)

from neo4j import GraphDatabase

URI  = "neo4j+ssc://ef937a24.databases.neo4j.io"
USER = os.getenv("NEO4J_USERNAME", "")
PWD  = os.getenv("NEO4J_PASSWORD", "")

print(f"URI:  {URI}")
print(f"USER: {USER}")
print()

# Step 1 - test basic query
print("Step 1: Basic query...")
d = GraphDatabase.driver(URI, auth=(USER, PWD))
d.verify_connectivity()
with d.session(database=None) as s:
    r = s.run("RETURN 1 as n").single()
    print(f"  OK: {r['n']}")
d.close()

# Step 2 - test write
print("Step 2: Write test...")
d = GraphDatabase.driver(URI, auth=(USER, PWD))
with d.session(database=None) as s:
    s.run("MERGE (n:TestNode {id:'test1'}) SET n.name='test'")
    c = s.run("MATCH (n:TestNode) RETURN count(n) as c").single()
    print(f"  TestNode count: {c['c']}")
    s.run("MATCH (n:TestNode) DETACH DELETE n")
    print(f"  Cleaned up OK")
d.close()

# Step 3 - load actual graph
print("Step 3: Loading wm101_graph.json...")
with open("wm101_graph.json") as f:
    data = json.load(f)
nodes = data["nodes"]
rels  = data["relationships"]
equip = data["metadata"]["equipment"]

d = GraphDatabase.driver(URI, auth=(USER, PWD))
with d.session(database=None) as s:
    s.run("MATCH (n) WHERE n.equip_tag=$e DETACH DELETE n", {"e": equip})
    for node in nodes:
        props = dict(node.get("properties", {}))
        props["_id"] = node["id"]
        props["_label"] = node["label"]
        props["_type"] = node["type"]
        props["equip_tag"] = equip
        label = node["type"].replace(" ", "_")
        s.run(f"MERGE (n:{label} {{_id: $id}}) SET n += $props",
              {"id": node["id"], "props": props})
    for rel in rels:
        s.run(f"MATCH (a {{_id:$f}}) MATCH (b {{_id:$t}}) MERGE (a)-[:{rel['type']}]->(b)",
              {"f": rel["from"], "t": rel["to"]})
    c = s.run("MATCH (n) WHERE n.equip_tag=$e RETURN count(n) as c", {"e": equip}).single()
    print(f"  Loaded: {c['c']} nodes")
d.close()

print("\n✅ All steps passed — neo4j+ssc:// works")
print(f"\nFIX for knowledge_graph.py:")
print(f"  Change URI to: neo4j+ssc://ef937a24.databases.neo4j.io")
print(f"  Or update .env: NEO4J_URI=neo4j+ssc://ef937a24.databases.neo4j.io")
